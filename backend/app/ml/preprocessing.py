from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union

import cv2
import numpy as np


@dataclass
class ImageRegion:
    row_index: int
    col_index: int
    bbox: Tuple[int, int, int, int]
    image: np.ndarray
    area: int


def load_image(image_path: Union[str, Path]) -> np.ndarray:
    """Load an image file from disk into an OpenCV matrix."""
    image_path = Path(image_path)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Unable to load image: {image_path}")
    return image


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a color image to grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise_image(gray: np.ndarray) -> np.ndarray:
    """Remove noise from a grayscale image while preserving edges."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        9,
    )


def correct_skew(gray: np.ndarray) -> np.ndarray:
    """Estimate and correct document skew using detected line orientation."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=20)
    if lines is None:
        return gray

    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 45:
            angles.append(angle)

    if not angles:
        return gray

    median_angle = np.median(angles)
    if abs(median_angle) < 0.1:
        return gray

    height, width = gray.shape[:2]
    center = (width // 2, height // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(gray, rotation_matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def detect_table_structure(binary_image: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Detect horizontal and vertical line structure for table segmentation."""
    height, width = binary_image.shape[:2]
    horizontal_size = max(10, width // 30)
    vertical_size = max(10, height // 30)

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size))

    horizontal = cv2.erode(binary_image, horizontal_kernel, iterations=1)
    horizontal = cv2.dilate(horizontal, horizontal_kernel, iterations=1)

    vertical = cv2.erode(binary_image, vertical_kernel, iterations=1)
    vertical = cv2.dilate(vertical, vertical_kernel, iterations=1)

    table_mask = cv2.addWeighted(horizontal, 0.5, vertical, 0.5, 0.0)
    table_mask = cv2.bitwise_or(table_mask, cv2.bitwise_and(horizontal, vertical))

    return table_mask, horizontal, vertical


def _extract_line_boxes(segment: np.ndarray, axis: str) -> List[Tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(segment, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 100]
    if axis == "horizontal":
        return [box for box in boxes if box[2] > box[3]]
    return [box for box in boxes if box[3] > box[2]]


def _sort_and_merge_positions(positions: List[int], min_gap: int = 15) -> List[int]:
    positions = sorted(set(positions))
    if not positions:
        return []

    merged = [positions[0]]
    for current in positions[1:]:
        if current - merged[-1] > min_gap:
            merged.append(current)
    return merged


def segment_table_cells(image: np.ndarray, horizontal: np.ndarray, vertical: np.ndarray) -> List[ImageRegion]:
    """Segment the detected table into structured row and column cells."""
    table_mask = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    table_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(table_contour)

    horizontal_boxes = _extract_line_boxes(horizontal, axis="horizontal")
    vertical_boxes = _extract_line_boxes(vertical, axis="vertical")

    row_centers = _sort_and_merge_positions([box[1] + box[3] // 2 for box in horizontal_boxes])
    col_centers = _sort_and_merge_positions([box[0] + box[2] // 2 for box in vertical_boxes])

    rows = [y] + [pos for pos in row_centers if y < pos < y + h] + [y + h]
    cols = [x] + [pos for pos in col_centers if x < pos < x + w] + [x + w]

    regions: List[ImageRegion] = []
    for row_index in range(len(rows) - 1):
        for col_index in range(len(cols) - 1):
            x1, y1 = cols[col_index], rows[row_index]
            x2, y2 = cols[col_index + 1], rows[row_index + 1]
            if x2 - x1 < 20 or y2 - y1 < 20:
                continue

            cell_image = image[y1:y2, x1:x2]
            regions.append(ImageRegion(
                row_index=row_index,
                col_index=col_index,
                bbox=(x1, y1, x2 - x1, y2 - y1),
                image=cell_image,
                area=int((x2 - x1) * (y2 - y1)),
            ))

    return regions


def preprocess_checklist_image(image_path: Union[str, Path]) -> List[ImageRegion]:
    """Run the full preprocessing pipeline and return segmented table regions."""
    image = load_image(image_path)
    gray = to_grayscale(image)
    denoised = denoise_image(gray)
    corrected = correct_skew(denoised)
    _, horizontal, vertical = detect_table_structure(corrected)
    regions = segment_table_cells(corrected, horizontal, vertical)
    return regions
