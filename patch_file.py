import re

def optimize_alpha_composite(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    helper = """
    def _fast_alpha_composite(self, base, overlay):
        \"\"\"Helper method to composite only the bounding box of an overlay.
        This is significantly faster than full-screen compositing.\"\"\"
        bbox = overlay.getbbox()
        if bbox:
            base.alpha_composite(overlay.crop(bbox), (bbox[0], bbox[1]))
        else:
            # If bbox is None, the overlay is completely transparent, so we don't need to composite anything
            pass
"""

    # Insert helper before render_theme_image using exact string match
    # find the index
    idx = content.find("    def _fast_alpha_composite(self, base, overlay):")
    if idx != -1:
        # replace the existing one
        end_idx = content.find("    def render_theme_image(self):", idx)
        content = content[:idx] + helper[1:] + "\n" + content[end_idx:]

    with open(filepath, 'w') as f:
        f.write(content)

optimize_alpha_composite('src/ui/main_window.py')
