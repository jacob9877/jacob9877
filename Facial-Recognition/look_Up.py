import os
import shutil
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

# Function to scrape actor images from IMDb
def scrape_actor_images_imdb(actor_name, num_images, output_directory, image_directory):
    # Search for the actor on IMDb
    search_url = f"https://www.imdb.com/find?q={actor_name}&s=nm"
    response = requests.get(search_url)

    if response.status_code == 200:
        # Parse the search results page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the link to the actor's profile page (assuming the first result is correct)
        profile_link = soup.find('td', class_='result_text').find('a')['href']
        profile_url = f"https://www.imdb.com{profile_link}"

        # Visit the actor's profile page
        profile_response = requests.get(profile_url)

        if profile_response.status_code == 200:
            profile_soup = BeautifulSoup(profile_response.text, 'html.parser')

            # Find the actor's images on their profile page (adjust the selector as needed)
            image_elements = profile_soup.select('.media_index_thumb_list img')

            if image_elements:
                # Create the output directory if it doesn't exist
                os.makedirs(output_directory, exist_ok=True)

                # Create a subdirectory for the images if it doesn't exist
                image_directory_path = os.path.join(output_directory, image_directory)
                os.makedirs(image_directory_path, exist_ok=True)

                for i, img in enumerate(image_elements):
                    if i >= num_images:
                        break
                    try:
                        # Get the image URL
                        img_url = img['src']

                        # Download the image
                        response = requests.get(img_url)

                        if response.status_code == 200:
                            image_data = Image.open(BytesIO(response.content))
                            image_path = os.path.join(image_directory_path, f"{actor_name}_{i + 1}.jpg")
                            image_data.save(image_path)
                            print(f"Downloaded image {i + 1} for {actor_name}")
                    except Exception as e:
                        print(f"Error downloading image {i + 1} for {actor_name}: {str(e)}")
            else:
                print(f"No images found for {actor_name} on IMDb.")
        else:
            print(f"Failed to access the actor's IMDb profile page.")
    else:
        print(f"Actor '{actor_name}' not found on IMDb.")




# Function to copy the training images to the validation folder
def copy_training_to_validation(source_directory, destination_directory):
    try:
        # Check if the destination directory exists; create it if not
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)

        # List all subdirectories in the source directory (each subdirectory represents a subject)
        subjects = os.listdir(source_directory)

        # Copy each subject's images to the corresponding subdirectory in the destination (validation) folder
        for subject in subjects:
            src_subject_dir = os.path.join(source_directory, subject)
            dest_subject_dir = os.path.join(destination_directory, subject)

            # Check if the subject's directory exists in the destination; create it if not
            if not os.path.exists(dest_subject_dir):
                os.makedirs(dest_subject_dir)

            # Copy images from source to destination
            for image_file in os.listdir(src_subject_dir):
                src_image_path = os.path.join(src_subject_dir, image_file)
                dest_image_path = os.path.join(dest_subject_dir, image_file)
                shutil.copy(src_image_path, dest_image_path)

        print(f"Successfully copied training images to validation folder: {destination_directory}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

def option():
    print("Looks up pictures")
    print("1. Download images for training")
    print("2. Copy training images to validation")
    print("3. Test the model")

    choice = int(input("Enter choice based on options: "))
    if choice == 1:
        celebrity_name = input("Enter the name of the subject: ")
        images = int(input("Enter the number of images to download: "))
        download_directory = "training"  # Replace with your desired training directory
        image_directory = celebrity_name  # Use the subject name as the image directory

        # Download images from IMDb
        scrape_actor_images_imdb(celebrity_name, images, download_directory, image_directory)

    elif choice == 2:
        source_directory = "training"  # Replace with your training directory
        destination_directory = "validation"  # Replace with your validation directory
        copy_training_to_validation(source_directory, destination_directory)
    elif choice == 3:
        # Call a function to test the model (not implemented in your code)
        pass
    else:
        print("Invalid choice. Please choose a valid option.")

if __name__ == "__main__":
    option()
