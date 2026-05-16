"""End-to-end checklist processing pipeline test."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.orchestrator import ChecklistProcessingOrchestrator


def test_pdf_processing():
    """Test processing a single PDF from sample folder."""
    print("\n" + "="*80)
    print("END-TO-END CHECKLIST PROCESSING TEST")
    print("="*80)
    
    # Find a sample PDF
    sample_dir = PROJECT_ROOT / "sample" / "April"
    pdf_files = list(sample_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("ERROR: No PDF files found in sample/April/")
        return False
    
    # Test with first PDF
    test_pdf = str(pdf_files[0])
    print(f"\nTest PDF: {Path(test_pdf).name}")
    
    # Initialize orchestrator without database (for testing)
    print("\nInitializing orchestrator...")
    orchestrator = ChecklistProcessingOrchestrator(db=None)
    
    # Process PDF
    print("\nProcessing PDF through pipeline...")
    result = orchestrator.process_pdf(test_pdf, persist=False)
    
    # Display results
    print("\n" + "-"*80)
    print("PROCESSING RESULT")
    print("-"*80)
    
    if result["success"]:
        print(f"Status: SUCCESS")
        print(f"Document: {result.get('document_id')}")
        print(f"Pages: {result.get('pages_processed')}")
        print(f"Regions: {result.get('regions_detected')}")
        print(f"Activities: {result.get('activities_extracted')}")
        
        # Display timeline events if extracted
        events = result.get('timeline_events', [])
        if events:
            print(f"\nTimeline Events ({len(events)}):")
            for event in events[:3]:  # Show first 3
                print(f"  - {event.get('start_time')} to {event.get('end_time')}: {event.get('event_type')}")
        
        # Display analytics if computed
        analytics = result.get('analytics')
        if analytics:
            ratios = analytics.get('performance_ratios', {})
            print(f"\nAnalytics Computed:")
            print(f"  - Utilization: {ratios.get('utilization_ratio', 0):.1%}")
            print(f"  - Downtime: {ratios.get('downtime_ratio', 0):.1%}")
        
        # Display processing log
        log = result.get('processing_log', [])
        print(f"\nProcessing Log ({len(log)} steps):")
        for entry in log:
            status = "[OK]" if entry['status'] == 'info' else f"[{entry['status'].upper()}]"
            print(f"  {status} [{entry['stage']}] {entry['message']}")
        
        return True
    else:
        print(f"Status: FAILED")
        print(f"Error: {result.get('error')}")
        
        # Display partial processing log
        log = result.get('processing_log', [])
        if log:
            print(f"\nProcessing Log (until failure):")
            for entry in log:
                print(f"  [{entry['stage']}] {entry['message']}")
        
        return False


def test_multiple_pdfs():
    """Test processing multiple PDFs from sample folder."""
    print("\n" + "="*80)
    print("BATCH PROCESSING TEST")
    print("="*80)
    
    sample_dir = PROJECT_ROOT / "sample" / "April"
    pdf_files = sorted(list(sample_dir.glob("*.pdf")))[:3]  # First 3 files
    
    if not pdf_files:
        print("ERROR: No PDF files found")
        return False
    
    print(f"\nProcessing {len(pdf_files)} PDFs from sample/April/")
    
    orchestrator = ChecklistProcessingOrchestrator(db=None)
    
    results = orchestrator.process_multiple_pdfs(str(sample_dir), limit=3)
    
    # Summary
    print("\n" + "-"*80)
    print("BATCH PROCESSING SUMMARY")
    print("-"*80)
    
    successful = sum(1 for r in results if r['success'])
    print(f"Total: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    
    for i, result in enumerate(results, 1):
        doc_id = result.get('document_id', 'unknown')
        status = "OK" if result['success'] else "FAIL"
        activities = result.get('activities_extracted', 0)
        print(f"  {i}. {doc_id}: {status} ({activities} activities)")
    
    return successful == len(results)


if __name__ == "__main__":
    try:
        # Run single file test
        single_ok = test_pdf_processing()
        
        # Run batch test
        batch_ok = test_multiple_pdfs()
        
        # Summary
        print("\n" + "="*80)
        if single_ok and batch_ok:
            print("ALL TESTS PASSED - Pipeline is operational!")
        else:
            print("Some tests failed - check PDF files and dependencies")
        print("="*80)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
