"""
3D box model generator
"""

from PIL import Image


class BoxGeometry:
    """3D box geometry data"""

    def __init__(self, width: float, height: float, depth: float):
        self.width = width
        self.height = height
        self.depth = depth

        # Generate vertices
        self.vertices = self._generate_vertices()
        self.faces = self._generate_faces()
        self.normals = self._generate_normals()

    def _generate_vertices(self) -> list[tuple[float, float, float]]:
        """Generate box vertices"""
        w, h, d = self.width / 2, self.height / 2, self.depth / 2

        return [
            # Front face (z+)
            (-w, -h, d),
            (w, -h, d),
            (w, h, d),
            (-w, h, d),
            # Back face (z-)
            (-w, -h, -d),
            (-w, h, -d),
            (w, h, -d),
            (w, -h, -d),
            # Left face (x-)
            (-w, -h, -d),
            (-w, -h, d),
            (-w, h, d),
            (-w, h, -d),
            # Right face (x+)
            (w, -h, -d),
            (w, h, -d),
            (w, h, d),
            (w, -h, d),
            # Top face (y+)
            (-w, h, -d),
            (-w, h, d),
            (w, h, d),
            (w, h, -d),
            # Bottom face (y-)
            (-w, -h, -d),
            (w, -h, -d),
            (w, -h, d),
            (-w, -h, d),
        ]

    def _generate_faces(self) -> list[tuple[int, int, int, int]]:
        """Generate face indices (quads)"""
        return [
            # Front face
            (0, 1, 2, 3),
            # Back face
            (4, 5, 6, 7),
            # Left face
            (8, 9, 10, 11),
            # Right face
            (12, 13, 14, 15),
            # Top face
            (16, 17, 18, 19),
            # Bottom face
            (20, 21, 22, 23),
        ]

    def _generate_normals(self) -> list[tuple[float, float, float]]:
        """Generate face normals"""
        return [
            (0, 0, 1),  # Front
            (0, 0, -1),  # Back
            (-1, 0, 0),  # Left
            (1, 0, 0),  # Right
            (0, 1, 0),  # Top
            (0, -1, 0),  # Bottom
        ]


class Box3DGenerator:
    """3D box model generator from 2D annotations"""

    def __init__(self):
        self.face_labels = ["Front", "Back", "Left", "Right", "Top", "Bottom"]

    def generate_from_crops(
        self, crops: list[dict], box_dimensions: tuple[float, float, float] = None
    ) -> BoxGeometry:
        """Generate 3D box from crop data"""

        if box_dimensions is None:
            # Estimate dimensions from crops
            box_dimensions = self._estimate_dimensions_from_crops(crops)

        width, height, depth = box_dimensions

        # Create box geometry
        geometry = BoxGeometry(width, height, depth)

        # Apply textures if crop images are available
        self._apply_crop_textures(geometry, crops)

        return geometry

    def _estimate_dimensions_from_crops(
        self, crops: list[dict]
    ) -> tuple[float, float, float]:
        """Estimate box dimensions from crop data"""
        if not crops:
            return (2.0, 1.5, 1.0)  # Default dimensions

        # Analyze crop sizes to estimate proportions
        face_sizes = {}
        for crop in crops:
            label = crop.get("label", "").lower()
            width = crop.get("width", 0)
            height = crop.get("height", 0)
            area = width * height

            if label and area > 0:
                face_sizes[label] = (width, height, area)

        # Estimate dimensions based on face relationships
        estimated_width = 2.0
        estimated_height = 1.5
        estimated_depth = 1.0

        # If we have front/back and left/right faces, we can estimate better
        if "front" in face_sizes and "left" in face_sizes:
            front_w, front_h, _ = face_sizes["front"]
            left_w, left_h, _ = face_sizes["left"]

            # Assume front face shows width x height
            # and left face shows depth x height
            if front_h > 0 and left_h > 0:
                height_ratio = left_h / front_h
                width_ratio = front_w / front_h
                depth_ratio = left_w / left_h

                # Normalize to reasonable proportions
                estimated_height = 1.5  # Reference height
                estimated_width = estimated_height * width_ratio * 1.2
                estimated_depth = estimated_height * depth_ratio * height_ratio

        # Clamp to reasonable ranges
        estimated_width = max(0.5, min(5.0, estimated_width))
        estimated_height = max(0.5, min(5.0, estimated_height))
        estimated_depth = max(0.5, min(5.0, estimated_depth))

        return (estimated_width, estimated_height, estimated_depth)

    def _apply_crop_textures(self, geometry: BoxGeometry, crops: list[dict]):
        """Apply crop images as textures to box faces"""
        # This would be used for texture mapping in advanced rendering
        # For now, we just store the association
        geometry.textures = {}

        for crop in crops:
            label = crop.get("label", "").lower()
            image = crop.get("image")  # PIL Image

            if label in [lb.lower() for lb in self.face_labels] and image:
                # Map label to face index
                face_mapping = {
                    "front": 0,
                    "back": 1,
                    "left": 2,
                    "right": 3,
                    "top": 4,
                    "bottom": 5,
                }

                if label in face_mapping:
                    face_index = face_mapping[label]
                    geometry.textures[face_index] = image

    def create_unfolded_template(
        self, geometry: BoxGeometry, crops: list[dict]
    ) -> Image.Image:
        """Create an unfolded box template from 3D geometry and crops"""

        # Calculate template dimensions
        w, h, d = geometry.width, geometry.height, geometry.depth

        # Template layout:
        #     +---+
        #     | T |    T = Top
        # +---+---+---+---+
        # | L | F | R | B |    L = Left, F = Front, R = Right, B = Back
        # +---+---+---+---+
        #     | Bot|    Bot = Bottom
        #     +---+

        # Scale factor for template (pixels per unit)
        scale = 100  # 100 pixels per unit

        template_width = int((w + d * 2) * scale)
        template_height = int((h * 2 + d) * scale)

        # Create template image
        template = Image.new("RGB", (template_width, template_height), "white")

        # Face positions in template
        face_positions = {
            "front": (int(d * scale), int(d * scale)),  # Center
            "back": (int((d + w + d) * scale), int(d * scale)),  # Right
            "left": (0, int(d * scale)),  # Left
            "right": (int((d + w) * scale), int(d * scale)),  # Right of front
            "top": (int(d * scale), 0),  # Top
            "bottom": (int(d * scale), int((d + h) * scale)),  # Bottom
        }

        face_sizes = {
            "front": (int(w * scale), int(h * scale)),
            "back": (int(w * scale), int(h * scale)),
            "left": (int(d * scale), int(h * scale)),
            "right": (int(d * scale), int(h * scale)),
            "top": (int(w * scale), int(d * scale)),
            "bottom": (int(w * scale), int(d * scale)),
        }

        # Apply crop images to template
        for crop in crops:
            label = crop.get("label", "").lower()
            image = crop.get("image")

            if label in face_positions and image:
                pos = face_positions[label]
                size = face_sizes[label]

                # Resize crop image to fit face
                resized_crop = image.resize(size, Image.Resampling.LANCZOS)

                # Paste onto template
                template.paste(resized_crop, pos)

        return template

    def export_obj(
        self, geometry: BoxGeometry, file_path: str, with_textures: bool = False
    ) -> bool:
        """Export box geometry to OBJ file"""
        try:
            with open(file_path, "w") as f:
                f.write("# BoxHunt 3D Box Export\n")
                f.write(
                    f"# Dimensions: {geometry.width:.2f} x {geometry.height:.2f} x {geometry.depth:.2f}\n\n"
                )

                # Write vertices
                for vertex in geometry.vertices:
                    f.write(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")

                f.write("\n")

                # Write texture coordinates if available
                if with_textures and hasattr(geometry, "textures"):
                    # Basic UV mapping for box
                    uvs = [
                        # Each face gets standard UV coordinates
                        (0, 0),
                        (1, 0),
                        (1, 1),
                        (0, 1),  # Front
                    ] * 6  # Repeat for all 6 faces

                    for uv in uvs:
                        f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

                    f.write("\n")

                # Write normals
                for i, _ in enumerate(geometry.faces):
                    normal = geometry.normals[i]
                    f.write(f"vn {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")

                f.write("\n")

                # Write faces
                for i, face_indices in enumerate(geometry.faces):
                    # Convert to 1-based indexing for OBJ
                    indices = [str(idx + 1) for idx in face_indices]

                    if with_textures and hasattr(geometry, "textures"):
                        # Include texture and normal indices
                        uv_base = i * 4 + 1
                        face_str = " ".join(
                            [
                                f"{idx}/{uv_base + j}/{i + 1}"
                                for j, idx in enumerate(indices)
                            ]
                        )
                    else:
                        # Just vertex and normal indices
                        face_str = " ".join([f"{idx}//{i + 1}" for idx in indices])

                    f.write(f"f {face_str}\n")

            return True

        except Exception as e:
            print(f"Error exporting OBJ: {e}")
            return False

    def export_gltf(self, geometry: BoxGeometry, file_path: str) -> bool:
        """Export box geometry to glTF file"""
        try:
            # This would require a glTF library like pygltflib
            # For now, just return False to indicate not implemented
            return False

        except Exception:
            return False
