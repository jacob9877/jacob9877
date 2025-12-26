import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from PIL import Image, ImageDraw
from mtcnn import MTCNN
from tqdm import tqdm
import pickle
import argparse
import os
import numpy as np
import face_recognition  # Add this import statement for face_recognition

DEFAULT_ENCODINGS_PATH = "output/encodings.pkl"
BOUNDING_BOX_COLOR = "blue"
TEXT_COLOR = "white"

parser = argparse.ArgumentParser(description="Recognize faces in an image")
parser.add_argument("--train", action="store_true", help="Train on input data")
parser.add_argument("--validate", action="store_true", help="Validate trained face recognition model")
parser.add_argument("--test", action="store_true", help="Test the face recognition model with an unknown image")
parser.add_argument("--recognition-model", default="hog", choices=["hog", "cnn"], help="which model to use for face recognition: hog (CPU), cnn (GPU)")
parser.add_argument("-f", action="store", help="Path to an image with an unknown face")
args = parser.parse_args()

TRAINING_DIR = "training"
VALIDATION_DIR = "validation"
OUTPUT_DIR = "output"

os.makedirs(TRAINING_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(VALIDATION_DIR, exist_ok=True)

# Create an MTCNN detector
detector = MTCNN()

def encode_known_faces_batch(filepaths, model="hog"):
    names = []
    encodings = []

    for filepath in filepaths:
        # Check if the file is a valid image file
        try:
            image = Image.open(filepath)
        except (OSError, Image.UnidentifiedImageError) as e:
            print(f"Skipping {filepath}: {e}")
            continue

        name = os.path.basename(os.path.dirname(filepath))
        pixels = image.convert("RGB")
        pixels = pixels.resize((160, 160))
        pixels = np.asarray(pixels)

        # Detect faces using MTCNN
        face_locations = detector.detect_faces(pixels)
        if len(face_locations) == 0:
            continue

        x, y, w, h = face_locations[0]['box']
        face = pixels[y:y+h, x:x+w]

        # Encode the detected face using face_recognition
        face_encodings = face_recognition.face_encodings(face)

        for encoding in face_encodings:
            names.append(name)
            encodings.append(encoding)

    return names, encodings

def encode_known_faces(model="hog", encodings_location=DEFAULT_ENCODINGS_PATH):
    filepaths = []
    for root, _, files in os.walk(TRAINING_DIR):
        for file in files:
            filepaths.append(os.path.join(root, file))

    batch_size = 100  # Adjust the batch size as needed
    with ThreadPoolExecutor() as executor:
        for i in range(0, len(filepaths), batch_size):
            batch_filepaths = filepaths[i:i + batch_size]
            names, encodings = executor.submit(encode_known_faces_batch, batch_filepaths, model).result()

    name_encodings = {"names": names, "encodings": encodings}
    with open(encodings_location, "wb") as f:
        pickle.dump(name_encodings, f)

def recognize_faces(image_location, model="hog", encodings_location=DEFAULT_ENCODINGS_PATH):
    with open(encodings_location, "rb") as f:
        loaded_encodings = pickle.load(f)
    input_image = Image.open(image_location)
    pixels = input_image.convert("RGB")
    pixels = pixels.resize((160, 160))
    pixels = np.asarray(pixels)

    # Detect faces using MTCNN
    face_locations = detector.detect_faces(pixels)
    input_face_encodings = []

    for face_location in face_locations:
        x, y, w, h = face_location['box']
        face = pixels[y:y+h, x:x+w]

        # Encode the detected face using face_recognition
        face_encoding = face_recognition.face_encodings(face)
        input_face_encodings.append(face_encoding)

    pillow_image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(pillow_image)

    for i, face_encoding in enumerate(input_face_encodings):
        name = _recognize_face(face_encoding, loaded_encodings)
        if not name:
            name = "Unknown"

        x, y, _, _ = face_locations[i]['box']
        _display_face(draw, x, y, name)

    del draw
    pillow_image.show()

def _recognize_face(unknown_encoding, loaded_encodings):
    boolean_matches = face_recognition.compare_faces(loaded_encodings["encodings"], unknown_encoding)
    votes = Counter(
        name
        for match, name in zip(boolean_matches, loaded_encodings["names"])
        if match
    )
    if votes:
        return votes.most_common(1)[0][0]

def _display_face(draw, x, y, name):
    draw.rectangle(((x, y), (x+160, y+160)), outline=BOUNDING_BOX_COLOR)
    draw.rectangle((x, y + 160, x + 160, y + 200), fill="blue", outline="blue")
    draw.text(
        (x + 10, y + 160),
        name,
        fill="white",
    )

def validate(model="hog"):
    filepaths = []
    for root, _, files in os.walk(VALIDATION_DIR):
        for file in files:
            filepaths.append(os.path.join(root, file))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for filepath in tqdm(filepaths, desc="Validating Faces"):
            executor.submit(recognize_faces, image_location=filepath, model=model)

if __name__ == "__main__":
    if args.train:
        encode_known_faces(model=args.recognition_model)
    if args.validate:
        validate(model=args.recognition_model)  # Use args.recognition_model here
    if args.test:
        recognize_faces(image_location=args.f, model=args.recognition_model)  # Use args.recognition_model here
