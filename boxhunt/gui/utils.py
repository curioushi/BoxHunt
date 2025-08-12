"""
GUI utility functions and helpers
"""

import sys

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """Convert PIL Image to QPixmap"""
    # Ensure image is in RGB or RGBA format
    if pil_image.mode not in ["RGB", "RGBA"]:
        pil_image = pil_image.convert("RGB")

    # Convert to QImage directly - no need to swap channels
    if pil_image.mode == "RGB":
        qimage = QImage(
            pil_image.tobytes(),
            pil_image.width,
            pil_image.height,
            pil_image.width * 3,  # bytes per line
            QImage.Format_RGB888,
        )
    else:  # RGBA
        qimage = QImage(
            pil_image.tobytes(),
            pil_image.width,
            pil_image.height,
            pil_image.width * 4,  # bytes per line
            QImage.Format_RGBA8888,
        )

    return QPixmap.fromImage(qimage)


def scale_image_to_fit(image: QPixmap, max_width: int, max_height: int) -> QPixmap:
    """Scale image to fit within given dimensions while maintaining aspect ratio"""
    if image.isNull():
        return image

    return image.scaled(
        max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


def get_screen_geometry() -> tuple[int, int]:
    """Get screen resolution"""
    if QApplication.instance() is None:
        QApplication(sys.argv)

    screen = QApplication.primaryScreen()
    geometry = screen.availableGeometry()
    return geometry.width(), geometry.height()


def clamp_rect(
    x: int, y: int, w: int, h: int, max_w: int, max_h: int
) -> tuple[int, int, int, int]:
    """Clamp rectangle coordinates to stay within bounds"""
    x = max(0, min(x, max_w - 1))
    y = max(0, min(y, max_h - 1))
    w = max(1, min(w, max_w - x))
    h = max(1, min(h, max_h - y))
    return x, y, w, h


def get_perspective_transform_matrix(
    src_points: list[tuple[float, float]], dst_points: list[tuple[float, float]]
) -> np.ndarray:
    """Calculate perspective transformation matrix from 4 source points to 4 destination points"""
    # Convert to numpy arrays
    src = np.array(src_points, dtype=np.float32)
    dst = np.array(dst_points, dtype=np.float32)

    # Create coefficient matrix A for the system of equations
    A = []
    b = []

    for i in range(4):
        x, y = src[i]
        u, v = dst[i]

        # For each point, we get 2 equations
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])

        b.extend([u, v])

    A = np.array(A, dtype=np.float32)
    b = np.array(b, dtype=np.float32)

    # Solve the system of equations
    try:
        h = np.linalg.solve(A, b)
        # Add the last element (h33 = 1) to complete the 3x3 matrix
        transform_matrix = np.append(h, 1.0).reshape(3, 3)
        return transform_matrix
    except np.linalg.LinAlgError:
        # Return identity matrix if calculation fails
        return np.eye(3, dtype=np.float32)


def apply_perspective_transform(
    image: Image.Image,
    src_points: list[tuple[int, int]],
    output_size: tuple[int, int] = (512, 512),
) -> Image.Image:
    """Apply perspective transformation to extract and rectify a quadrilateral region

    Extracts the polygon region defined by src_points and transforms it to fill
    the entire output image:
    - src_points[0] (polygon corner) -> top-left corner (0, 0)
    - src_points[1] (polygon corner) -> bottom-left corner (0, 512)
    - src_points[2] (polygon corner) -> bottom-right corner (512, 512)
    - src_points[3] (polygon corner) -> top-right corner (512, 0)
    """
    try:
        if len(src_points) != 4:
            raise ValueError(f"Expected 4 source points, got {len(src_points)}")

        # Define destination points (corners of output rectangle)
        # We want to map polygon region to fill the entire 512x512 output
        width, height = output_size
        dst_points = [
            (0, 0),  # 左上角
            (0, height),  # 左下角
            (width, height),  # 右下角
            (width, 0),  # 右上角
        ]

        # PIL transform uses inverse transformation, so we need to swap src and dst
        # This will extract the polygon region and map it to fill the output rectangle
        coeffs = get_perspective_coefficients(dst_points, src_points)

        # Apply the transformation
        transformed = image.transform(
            output_size,
            Image.PERSPECTIVE,
            coeffs,
            resample=Image.BICUBIC,
            fillcolor=(255, 255, 255),
        )

        return transformed

    except Exception as e:
        print(f"Perspective transform error: {e}")
        print(f"Source points: {src_points}")
        print(f"Output size: {output_size}")

        # Fallback: create a simple crop of the bounding box
        if len(src_points) >= 4:
            xs = [p[0] for p in src_points]
            ys = [p[1] for p in src_points]
            bbox = (min(xs), min(ys), max(xs), max(ys))

            try:
                cropped = image.crop(bbox)
                return cropped.resize(output_size, Image.BICUBIC)
            except Exception:
                pass

        # Ultimate fallback: return empty image
        return Image.new("RGB", output_size, (240, 240, 240))


def get_perspective_coefficients(
    src_points: list[tuple[int, int]], dst_points: list[tuple[int, int]]
) -> tuple[float, ...]:
    """Calculate perspective transformation coefficients for PIL"""
    try:
        # Convert points to numpy arrays
        src = np.array(src_points, dtype=np.float32)
        dst = np.array(dst_points, dtype=np.float32)

        # Set up the system of equations
        # For PIL perspective transform, we need 8 coefficients (a, b, c, d, e, f, g, h)
        # The transformation is: x' = (ax + by + c) / (gx + hy + 1)
        #                        y' = (dx + ey + f) / (gx + hy + 1)

        # Create the coefficient matrix
        A = []
        B = []

        for i in range(4):
            x, y = src[i]
            u, v = dst[i]

            A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
            A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
            B.extend([u, v])

        A = np.array(A)
        B = np.array(B)

        # Solve for coefficients
        coeffs = np.linalg.solve(A, B)

        return tuple(coeffs)

    except Exception as e:
        print(f"Coefficient calculation error: {e}")
        # Return identity transformation coefficients
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
