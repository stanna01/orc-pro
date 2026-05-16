"""Checklist processing orchestrator - coordinates entire pipeline."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import date
from tempfile import NamedTemporaryFile

from sqlalchemy.orm import Session

from backend.app.models.checklist import ChecklistForm
from backend.app.models.schemas import OCROutput
from backend.app.services.pdf_processor import (
    extract_pages_from_pdf,
    preprocess_image,
    detect_table_regions,
    extract_region,
    scale_image,
)
from backend.app.services.ocr_extractor import TrOCRExtractor, CONF_LOW
from backend.app.services.checklist_parser import ChecklistParser
from backend.app.services.ocr_rule_engine_integration import (
    integrate_ocr_with_rule_engine,
)
from backend.app.services.validator import validate_checklist

logger = logging.getLogger(__name__)


class ChecklistProcessingOrchestrator:
    """Orchestrates end-to-end checklist processing pipeline.
    
    Pipeline stages:
    1. PDF Upload → Extract pages as images
    2. Preprocessing → Enhance images for OCR
    3. OCR Extraction → Extract text using TrOCR
    4. Post-Processing → Parse text to structured data
    5. Rule Engine → Apply business logic
    6. Analytics → Compute performance metrics
    7. Database → Persist results
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize orchestrator.
        
        Args:
            db: Optional SQLAlchemy session for database operations
        """
        self.db = db
        self.ocr_extractor = TrOCRExtractor()
        self.parser = ChecklistParser()
        self.processing_log = []

    def apply_confidence_filter(self, extracted_texts: List[Dict[str, Any]], threshold: float = CONF_LOW) -> Dict[str, Any]:
        """Apply confidence-based filtering and produce header/activity blobs.

        Returns dict with keys: header_blob, activity_texts, issues
        """
        issues = []
        # choose first two regions as header candidates
        header_regions = extracted_texts[:2] if len(extracted_texts) >= 2 else extracted_texts[:1]
        header_texts = []
        header_confs = []
        header_class = None
        for r in header_regions:
            txt = r.get("text", "")
            conf = r.get("confidence")
            cls = r.get("classification")
            if not txt or (isinstance(conf, float) and conf < threshold):
                issues.append({"stage": "CONFIDENCE_FILTER", "region_index": r.get("region_index"), "issue": "low_confidence_or_empty"})
            else:
                header_texts.append(txt)
                header_confs.append(conf)
                header_class = cls or header_class

        header_blob = {
            "text": " ".join(header_texts) if header_texts else "",
            "confidence": float(sum(header_confs) / len(header_confs)) if header_confs else 0.0,
            "classification": header_class,
        }

        # Remaining regions are activity rows
        activity_regions = extracted_texts[2:] if len(extracted_texts) > 2 else extracted_texts[1:]
        activity_texts = []
        for r in activity_regions:
            txt = r.get("text", "")
            conf = r.get("confidence")
            if not txt:
                # try to use re_segments if available
                reseg = r.get("re_segments") or []
                merged = []
                for s in reseg:
                    if s.get("text") and (s.get("confidence") is None or s.get("confidence") >= threshold):
                        merged.append(s.get("text"))
                if merged:
                    activity_texts.append(" ".join(merged))
                    continue
                issues.append({"stage": "CONFIDENCE_FILTER", "region_index": r.get("region_index"), "issue": "empty_after_filter"})
                # still append empty to keep row positions
                activity_texts.append("")
            else:
                # if low confidence, mark but still include for parser to attempt parsing
                if isinstance(conf, float) and conf < threshold:
                    issues.append({"stage": "CONFIDENCE_FILTER", "region_index": r.get("region_index"), "issue": "low_confidence_included"})
                activity_texts.append(txt)

        return {"header_blob": header_blob, "activity_texts": activity_texts, "issues": issues}

    def process_from_extracted_regions(self, extracted_texts: List[Dict[str, Any]], reference_date: Optional[date] = None, persist: bool = False) -> Dict[str, Any]:
        """Run the strict pipeline starting from OCR-extracted regions.

        This enforces the ordered stages:
          OCR -> Confidence Filter -> Parser -> Validation -> Timeline -> Rule Engine -> Analytics
        Returns a detailed trace and outputs.
        """
        self.processing_log = []
        if reference_date is None:
            reference_date = date.today()

        # Stage: Confidence Filter
        self.log_step("CONFIDENCE_FILTER", "Applying confidence-based filtering")
        cf = self.apply_confidence_filter(extracted_texts)
        for iss in cf.get("issues", []):
            self.log_step("CONFIDENCE_FILTER", f"Issue: {iss}", status="warning")

        # Stage: Parser
        self.log_step("PARSING", "Parsing filtered OCR outputs")
        header_blob = cf.get("header_blob")
        activity_texts = cf.get("activity_texts")
        ocr_output = self.parser.parse_checklist(header_blob, activity_texts, document_id="synthetic_doc")
        self.log_step("PARSING", f"Parsed {len(ocr_output.activities)} activities; header confidence={ocr_output.processing_metadata.get('confidence_average')}")

        # Stage: Validation
        self.log_step("VALIDATION", "Running strict validation checks before rule engine")
        validation_report = validate_checklist(ocr_output)
        if validation_report.errors:
            for err in validation_report.errors:
                sev = 'warning' if err.severity == 'warning' else 'error'
                self.log_step("VALIDATION", f"{err.severity.upper()}: {err.message} rows={err.affected_rows}", status=sev)

        if validation_report.needs_review:
            self.log_step("VALIDATION", "Critical validation errors detected; halting automatic pipeline", status="error")
            return {"success": False, "stage": "VALIDATION", "validation_report": validation_report, "processing_log": self.processing_log}

        # Stage: Timeline & Rule Engine & Analytics (via integration helper)
        self.log_step("RULE_ENGINE", "Converting OCR -> rule engine and processing timeline")
        integration_result = integrate_ocr_with_rule_engine(db=self.db, ocr_output=ocr_output, checklist_form=None, reference_date=reference_date)
        self.log_step("RULE_ENGINE", "Rule engine and analytics complete")

        return {
            "success": True,
            "ocr_output": ocr_output,
            "integration_result": integration_result,
            "processing_log": self.processing_log,
        }
    
    def log_step(self, stage: str, message: str, status: str = "info"):
        """Log processing step.
        
        Args:
            stage: Pipeline stage name
            message: Log message
            status: Log level (info, warning, error)
        """
        log_entry = {
            "stage": stage,
            "message": message,
            "status": status,
        }
        self.processing_log.append(log_entry)
        
        log_func = getattr(logger, status, logger.info)
        log_func(f"[{stage}] {message}")
    
    def process_pdf(
        self,
        pdf_path: str,
        reference_date: Optional[date] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Process checklist PDF end-to-end.
        
        Args:
            pdf_path: Path to PDF file
            reference_date: Optional reference date for shift anchoring
            persist: Whether to persist results to database
            
        Returns:
            Processing result with extracted data, timeline, and analytics
        """
        if reference_date is None:
            reference_date = date.today()
        
        self.processing_log = []
        
        try:
            # Stage 1: Extract PDF pages
            self.log_step("PDF_EXTRACTION", f"Opening PDF: {pdf_path}")
            pages = extract_pages_from_pdf(pdf_path)
            self.log_step("PDF_EXTRACTION", f"Extracted {len(pages)} pages")
            
            if not pages:
                raise ValueError("No pages extracted from PDF")
            
            # Process first page (main checklist)
            page = pages[0]
            self.log_step("PDF_EXTRACTION", f"Processing page 1 ({page.shape})")
            
            # Stage 2: Preprocess image
            self.log_step("PREPROCESSING", "Enhancing image quality")
            preprocessed = preprocess_image(page)
            self.log_step("PREPROCESSING", "Image preprocessing complete")
            
            # Stage 3: Detect regions and extract text via OCR
            self.log_step("REGION_DETECTION", "Detecting table regions")
            regions = detect_table_regions(preprocessed)
            self.log_step("REGION_DETECTION", f"Detected {len(regions)} regions")
            
            if not regions:
                raise ValueError("No table regions detected in PDF")
            
            # Extract text from regions
            self.log_step("OCR_EXTRACTION", f"Running TrOCR on {len(regions)} regions")
            extracted_texts = self.ocr_extractor.extract_text_from_regions(preprocessed, regions)
            self.log_step("OCR_EXTRACTION", f"Extracted text from {len(extracted_texts)} regions")
            
            # Stage 4: Parse extracted text
            self.log_step("PARSING", "Parsing extracted text to structured format")
            
            # Separate header and activity rows
            # Build header blob from first one or two regions with aggregated confidence
            if len(extracted_texts) > 0:
                header_regions = extracted_texts[:2]
                header_text = " ".join([r.get("text", "") for r in header_regions])
                # average confidence
                confs = [r.get("confidence") for r in header_regions if r.get("confidence") is not None]
                header_conf = float(sum(confs) / len(confs)) if confs else 0.0
                # worst classification if present
                classifications = [r.get("classification") for r in header_regions if r.get("classification")]
                header_class = classifications[-1] if classifications else None
                header_blob = {"text": header_text, "confidence": header_conf, "classification": header_class}
            else:
                header_blob = {"text": "", "confidence": 0.0, "classification": "unreadable"}

            activity_texts = extracted_texts[2:] if len(extracted_texts) > 2 else []
            
            # Parse to OCROutput
            document_id = Path(pdf_path).stem
            ocr_output = self.parser.parse_checklist(header_blob, activity_texts, document_id)
            self.log_step("PARSING", f"Parsed {len(ocr_output.activities)} activities")
            
            # Stage 5: Validate parsed checklist BEFORE rule engine
            self.log_step("VALIDATION", "Running strict validation checks before rule engine")
            validation_report = validate_checklist(ocr_output)
            if validation_report.errors:
                # log errors
                for err in validation_report.errors:
                    sev = 'warning' if err.severity == 'warning' else 'error'
                    self.log_step("VALIDATION", f"{err.severity.upper()}: {err.message} rows={err.affected_rows}", status=sev)
            # If any critical errors exist, halt further automatic rule-engine processing
            if validation_report.needs_review:
                # Persist validation into response and stop pipeline to prevent silent pass
                self.log_step("VALIDATION", "Critical validation errors detected; flagging checklist for manual review", status="error")
                result = {
                    "success": False,
                    "document_id": document_id,
                    "validation_report": validation_report,
                    "processing_log": self.processing_log,
                }
                # Do not proceed to rule engine — caller must perform review/correction
                return result

            # Stage 6-7: Process through rule engine and analytics
            self.log_step("RULE_ENGINE", "Processing through rule engine")
            
            # Create or get checklist form if persisting
            checklist_form = None
            if persist and self.db:
                checklist_form = ChecklistForm(
                    source_filename=document_id,
                    document_date=reference_date,
                    machine_number=ocr_output.header.machine_id.value,
                    operator_name=ocr_output.header.operator_name.value,
                    shift=ocr_output.header.shift.value,
                    start_engine_hours=self._parse_float(
                        ocr_output.header.engine_hours_start.value
                    ),
                    end_engine_hours=self._parse_float(
                        ocr_output.header.engine_hours_end.value
                    ),
                )
                self.db.add(checklist_form)
                self.db.flush()
                self.log_step("DATABASE", f"Created checklist form (ID: {checklist_form.id})")
            
            # Integrate with rule engine
            integration_result = integrate_ocr_with_rule_engine(
                db=self.db,
                ocr_output=ocr_output,
                checklist_form=checklist_form,
                reference_date=reference_date,
            )
            self.log_step("RULE_ENGINE", "Rule engine processing complete")
            
            # Log analytics computation
            if integration_result.get("analytics"):
                analytics = integration_result["analytics"]
                availability = analytics.get("availability_breakdown", {})
                ratios = analytics.get("performance_ratios", {})
                self.log_step(
                    "ANALYTICS",
                    f"Computed metrics: availability={ratios.get('availability_ratio', 0):.1%}, "
                    f"utilization={ratios.get('utilization_ratio', 0):.1%}"
                )
            
            # Commit if persisting
            if persist and self.db:
                self.db.commit()
                self.log_step("DATABASE", "Results persisted to database")
            
            # Prepare response
            result = {
                "success": True,
                "document_id": document_id,
                "pages_processed": len(pages),
                "regions_detected": len(regions),
                "activities_extracted": len(ocr_output.activities),
                "ocr_output": ocr_output,
                "timeline_events": integration_result.get("events", []),
                "timeline_summary": integration_result.get("summary", {}),
                "analytics": integration_result.get("analytics"),
                "persisted": {
                    "checklist_id": checklist_form.id if checklist_form else None,
                    "event_ids": integration_result.get("persisted_events", []),
                    "analytics_id": integration_result.get("persisted_analytics"),
                } if persist else None,
                "processing_log": self.processing_log,
            }
            
            return result
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            self.log_step("ERROR", error_msg, status="error")
            
            if self.db:
                self.db.rollback()
            
            return {
                "success": False,
                "error": str(e),
                "processing_log": self.processing_log,
            }
    
    def process_multiple_pdfs(
        self,
        pdf_directory: str,
        pattern: str = "*.pdf",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Process multiple PDF files in a directory.
        
        Args:
            pdf_directory: Directory containing PDF files
            pattern: File pattern to match (default: *.pdf)
            limit: Maximum number of files to process
            
        Returns:
            List of processing results
        """
        pdf_dir = Path(pdf_directory)
        pdf_files = sorted(pdf_dir.glob(pattern))
        
        if limit:
            pdf_files = pdf_files[:limit]
        
        results = []
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            result = self.process_pdf(str(pdf_file), persist=True)
            results.append(result)
            
            if not result["success"]:
                print(f"  ERROR: {result.get('error')}")
            else:
                print(f"  OK: {result['activities_extracted']} activities extracted")
        
        return results
    
    @staticmethod
    def _parse_float(value: str) -> Optional[float]:
        """Parse float from string value.
        
        Args:
            value: String value (may be empty or invalid)
            
        Returns:
            Float value or None
        """
        if not value or value.strip() == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def create_orchestrator(db: Optional[Session] = None) -> ChecklistProcessingOrchestrator:
    """Factory function to create orchestrator instance.
    
    Args:
        db: Optional SQLAlchemy session
        
    Returns:
        ChecklistProcessingOrchestrator instance
    """
    return ChecklistProcessingOrchestrator(db)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Initialize orchestrator (without database for testing)
    orchestrator = create_orchestrator(db=None)
    
    # Process PDF
    result = orchestrator.process_pdf(pdf_path, persist=False)
    
    # Print results
    print("\n" + "="*80)
    print("PROCESSING RESULTS")
    print("="*80)
    print(f"Success: {result['success']}")
    print(f"Document: {result.get('document_id')}")
    print(f"Activities: {result.get('activities_extracted', 0)}")
    print(f"\nProcessing Log:")
    for log in result.get('processing_log', []):
        print(f"  [{log['stage']}] {log['message']}")
