This project is a Python-based facial recognition system that allows you to train a model on a dataset of known faces, validate the model's accuracy, and recognize faces in unknown images. It uses the face_recognition library and provides command-line options for training, validation, and testing the model. The recognized faces are highlighted with bounding boxes and labeled with their names in a graphical user interface.

Facial recognition is a popular and widely used technology with applications in security, surveillance, and various other fields. This project provides a Python-based implementation of a facial recognition system that can be used for training, validation, and recognition tasks.

Key Features:

Training: Harness the potential of the system by training your facial recognition model with a dataset of known faces. Choose between the CPU-efficient "hog" model and the GPU-accelerated "cnn" model for optimal performance.

Validation: Post-training, assess your model's accuracy with precision using a dedicated validation dataset. The validation process provides clear visual feedback by showcasing recognized faces within validation images, allowing for a thorough evaluation of model performance.

Testing: Put your trained model to the test by identifying faces within unknown images. Simply provide the path to an image containing unidentified faces, and the system seamlessly identifies and annotates recognized faces, streamlining the recognition process.

Customizable Output: Recognized faces receive special treatment with striking blue bounding boxes and white text labels set against a blue background. This visually intuitive representation simplifies the identification of recognized faces, ensuring a user-friendly experience for all.


Dependencies:
    face_recognition: Used for face detection and recognition.
    Pillow: Used for image processing and drawing bounding boxes.
    pickle: Used for serializing and deserializing data.
    argparse: Used for command-line argument parsing.
    mtcnn: Used for face detection with the MTCNN (Multi-task Cascaded Convolutional Networks) model.
    numpy: Used for numerical operations and handling image data.
    tqdm: Used for creating progress bars for tasks such as validation.
