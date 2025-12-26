To use this project:

1. **Training the Model**:
   - To train the model, use the `--train` flag.
   - Specify the model type with the `--recognition-model` flag, choosing between "hog" (CPU-based) or "cnn" (GPU-based) models.
   - Example: `python3 detector.py --train --recognition-model hog`

   The trained face encodings will be saved in a file.

2. **Model Validation**:
   - To validate the trained model, use the `--validate` flag.
   - Specify the model type with the `--recognition-model` flag, again choosing between "hog" or "cnn" models.
   - This will display recognized faces in validation images.

   Example: `python3 detector.py --validate --recognition-model cnn`

3. **Testing with an Unknown Image**:
   - To test the model with an image containing unknown faces, use the `--test` flag.
   - Provide the path to the image with unknown faces using the `-f` flag.
   - Specify the model type with the `--recognition-model` flag (either "hog" or "cnn").

   Example: `python3 detector.py --test -f path/to/unknown_image.jpg --recognition-model hog`

Choose the appropriate flags and options according to your task, whether it's training, validating, or testing the face recognition model.
