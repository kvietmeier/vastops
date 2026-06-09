###### Flask Application for Image Upload and Annotate Only ######

import os
import random
from flask import Flask, send_file, render_template, redirect, url_for, request, jsonify
from PIL import Image, ImageDraw, ImageFont


app = Flask(__name__)

# --- Configuration ---
IMAGE_FOLDER = '/mnt/vast/gns_demo/images'
PROCESSED_FOLDER = '/mnt/vast/gns_demo/processed'

# !!! IMPORTANT: SET THE ROLE FOR THIS SERVER !!!
# Use 'producer' for the read-only server, 'editor' for the processing server
APP_ROLE = 'editor' # <-- CHANGE THIS LINE on the Editor server to 'editor'

os.makedirs(PROCESSED_FOLDER, exist_ok=True)


def annotate_image(input_path, output_path, reviewer_name="Reviewed by: Karl"):
    image = Image.open(input_path).convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)

    # --- Font and Text Annotation ---
    proportional_font_size = max(12, width // 40)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", proportional_font_size)
    except IOError:
        font = ImageFont.load_default()

    text_position = (10, 10)
    shadow_offset = 1
    draw.text((text_position[0] + shadow_offset, text_position[1] + shadow_offset), reviewer_name, font=font, fill="black")
    draw.text(text_position, reviewer_name, font=font, fill="white")


    # --- Draw Obvious Random Red Rectangle ---
    
    # 🌟 FIX: Guarantee a visible, non-narrow box
    ABSOLUTE_MIN_DIM = 150 # Ensure box dimension is at least 150 pixels
    
    # Define proportional maximums (Max 1/3 of the image size)
    max_box_width = width // 3
    max_box_height = height // 3

    # Ensure the minimum is large enough (max of 150px or 20% proportional size)
    effective_min_width = max(ABSOLUTE_MIN_DIM, int(width * 0.20))
    effective_min_height = max(ABSOLUTE_MIN_DIM, int(height * 0.20))

    # Calculate box dimensions, constraining the random range by the effective minimum and the available maximum
    box_width = random.randint(effective_min_width, min(max_box_width, width - 10))
    box_height = random.randint(effective_min_height, min(max_box_height, height - 10))

    # Calculate box position
    max_x = width - box_width
    max_y = height - box_height

    box_x = random.randint(0, max_x)
    box_y = random.randint(0, max_y)

    box_coords = [(box_x, box_y), (box_x + box_width, box_y + box_height)]
    
    # 🌟 FIX: Use a thick line width (width=8)
    draw.rectangle(box_coords, outline="red", width=15) 

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path, format='JPEG', quality=95)

    return output_path, box_coords


@app.route('/')
def index():
    images = []
    for filename in sorted(os.listdir(IMAGE_FOLDER)): 
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            processed_name = f"processed_{filename}"
            processed_path = os.path.join(PROCESSED_FOLDER, processed_name)
            images.append({
                "filename": filename,
                "processed_name": processed_name,
                "processed": os.path.exists(processed_path)
            })
    
    # 🌟 FIX: Corrected typo 'imagesi' -> 'images'
    return render_template('index.html', images=images, app_role=APP_ROLE) 

@app.route('/images/<filename>')
def image_file(filename):
    return send_file(os.path.join(IMAGE_FOLDER, filename), mimetype='image/jpeg')

@app.route('/processed/<filename>')
def processed_file(filename):
    path = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    else:
        return f"Processed image {filename} not found.", 404

@app.route('/process/<filename>')
def process_image(filename):
    input_path = os.path.join(IMAGE_FOLDER, filename)
    output_filename = f"processed_{filename}"
    output_path = os.path.join(PROCESSED_FOLDER, output_filename)

    annotate_image(input_path, output_path)

    return redirect(url_for('index'))

@app.route('/api/image_count')
def image_count():
    # 🌟 FIX: Returns both counts for client-side polling
    try:
        # 1. Count original files
        original_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        original_count = len(original_files)
        
        # 2. Count processed files
        processed_files = [f for f in os.listdir(PROCESSED_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        processed_count = len(processed_files)
        
        return jsonify({
            'original_count': original_count, 
            'processed_count': processed_count 
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
