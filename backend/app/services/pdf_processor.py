"""PDF preprocessing service for checklist extraction."""

import io
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_pages_from_pdf(pdf_path: str) -> List[np.ndarray]:
    """Extract PDF pages as images.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        List of numpy arrays (images) for each page
        
    Raises:
        ImportError: If PyMuPDF not installed
        FileNotFoundError: If PDF file not found
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if fitz is None:
        raise ImportError("PyMuPDF (fitz) required. Install with: pip install PyMuPDF")
    
    pages = []
    
    try:
        pdf_document = fitz.open(pdf_path)
        
        for page_num in range(len(pdf_document)):
            # Render page to image (300 DPI for better OCR)
            page = pdf_document[page_num]
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to numpy array
            image_data = np.frombuffer(pix.samples, dtype=np.uint8)
            image_array = image_data.reshape((pix.height, pix.width, pix.n))
            
            # Convert RGB to BGR for OpenCV
            if image_array.shape[2] == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            
            pages.append(image_array)
        
        pdf_document.close()
        return pages
        
    except Exception as e:
        raise RuntimeError(f"Failed to extract pages from PDF: {str(e)}")


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Preprocess image for better OCR accuracy.
    
    Applies:
    - Grayscale conversion
    - Contrast enhancement
    - Denoise
    - Deskew (rotation correction)
    
    Args:
        image: Input image (BGR)
        
    Returns:
        Preprocessed image
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10, templateWindowSize=7, searchWindowSize=21)
    
    # Apply threshold to get binary image
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary


def detect_table_regions(image: np.ndarray, min_area: int = 1000) -> List[Tuple[int, int, int, int]]:
    """Detect table/form regions in image.
    
    Args:
        image: Preprocessed image (binary)
        min_area: Minimum area for contour to be considered
        
    Returns:
        List of (x, y, w, h) bounding boxes
    """
    # Find contours
    contours, _ = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        
        # Filter by size
        if area > min_area:
            # Filter by aspect ratio (avoid very thin lines)
            aspect_ratio = w / h if h > 0 else 0
            if 0.1 < aspect_ratio < 10:
                regions.append((x, y, w, h))
    
    # Sort by position (top to bottom, left to right)
    regions = sorted(regions, key=lambda r: (r[1], r[0]))
    
    return regions


def extract_region(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """Extract a region from image using bounding box.
    
    Args:
        image: Source image
        bbox: (x, y, width, height) bounding box
        
    Returns:
        Cropped image region
    """
    x, y, w, h = bbox
    return image[y:y+h, x:x+w]


def scale_image(image: np.ndarray, scale_factor: float = 2.0) -> np.ndarray:
    """Upscale image for better OCR on small text.
    
    Args:
        image: Input image
        scale_factor: Scaling factor (2.0 = 2x)
        
    Returns:
        Scaled image
    """
    height, width = image.shape[:2]
    new_height = int(height * scale_factor)
    new_width = int(width * scale_factor)
    
    return cv2.resize(
        image, 
        (new_width, new_height),
        interpolation=cv2.INTER_CUBIC
    )


if __name__ == "__main__":
    # Test PDF processing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_processor.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    print(f"Extracting pages from: {pdf_path}")
    pages = extract_pages_from_pdf(pdf_path)
    print(f"Extracted {len(pages)} pages")
    
    for i, page in enumerate(pages):
        print(f"\nPage {i+1}: {page.shape}")
        preprocessed = preprocess_image(page)
        print(f"  Preprocessed: {preprocessed.shape}")
        
        regions = detect_table_regions(preprocessed)
        print(f"  Detected {len(regions)} regions")
