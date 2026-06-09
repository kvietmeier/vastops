###### Flask Application for Image Upload and Annotate Only ######
# This Flask app lists original images and their processed (annotated) versions.
# Users can manually trigger annotation (no resize) of images.
# Processed images are saved separately.
# The app serves original and processed images for viewing in the browser.
#
# Usage:
# 1. Put images into /mnt/vast/gns_demo/images
# 2. Run this script
# 3. Access http://localhost:8080 or http://<server-ip>:8080 in your browser

import os
import random
from flask import Flask, send_file, render_template, redirect, url_for, request, jsonify
from PIL import Image, ImageDraw, ImageFont


app = Flask(__name__)

IMAGE_FOLDER = '/mnt/vast/gns_demo/images'
PROCESSED_FOLDER = '/mnt/vast/gns_demo/processed'
APP_ROLE = 'producer'


os.makedirs(PROCESSED_FOLDER, exist_ok=True)


def annotate_image(input_path, output_path, reviewer_name="Reviewed by: Karl"):
    # Note: Using "Karl" as a placeholder. Your actual version might use "Maria" or be dynamic.
    image = Image.open(input_path).convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)

    # --- Font size proportional to image width ---
    proportional_font_size = max(12, width // 40)
    try:
        # Using a generic font path; adjust if needed for your system's font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", proportional_font_size)
    except IOError:
        font = ImageFont.load_default()

    # --- Draw reviewer name ---
    text_position = (10, 10)
    # Drawing white shadow for contrast (using black offset)
    shadow_offset = 1
    draw.text((text_position[0] + shadow_offset, text_position[1] + shadow_offset), reviewer_name, font=font, fill="black")
    draw.text(text_position, reviewer_name, font=font, fill="white")


    # --- Draw random red rectangle ---
    min_box_size = 50
    max_box_width = width // 3
    max_box_height = height // 3

    box_width = random.randint(min_box_size, max_box_width)
    box_height = random.randint(min_box_size, max_box_height)

    max_x = width - box_width
    max_y = height - box_height

    box_x = random.randint(0, max_x)
    box_y = random.randint(0, max_y)

    box_coords = [(box_x, box_y), (box_x + box_width, box_y + box_height)]
    draw.rectangle(box_coords, outline="red", width=3)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path, format='JPEG', quality=95)

    return output_path, box_coords

@app.route('/')
def index():
    images = []
    # Sorting ensures new files appear predictably
    for filename in sorted(os.listdir(IMAGE_FOLDER)): 
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            processed_name = f"processed_{filename}"
            processed_path = os.path.join(PROCESSED_FOLDER, processed_name)
            images.append({
                "filename": filename,
                "processed_name": processed_name,
                "processed": os.path.exists(processed_path)
            })
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
    # --- THIS IS THE CRUCIAL, MODIFIED ROUTE ---
    # It returns both counts, which the client-side JavaScript polls to refresh the page.
    try:
        # 1. Count original files (signals a new row in the gallery)
        original_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        original_count = len(original_files)
        
        # 2. Count processed files (signals a status change in an existing row)
        processed_files = [f for f in os.listdir(PROCESSED_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        processed_count = len(processed_files)
        
        # Return both counts to the client
        return jsonify({
            'original_count': original_count, 
            'processed_count': processed_count 
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Flask runs normally, relying on client-side polling for updates
    app.run(host='0.0.0.0', port=8080)
