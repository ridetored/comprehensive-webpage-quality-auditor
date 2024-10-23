import requests
from bs4 import BeautifulSoup
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# Helper function to clean and extract keywords from a text (meta title, description, alt attributes)
def extract_keywords(text):
    words = re.findall(r'\w+', text.lower())
    return set(words)

# Function to count the number of words on the page
def count_words(content):
    words = re.findall(r'\w+', content.lower())
    return len(words), set(words)

# Function to check image alt attributes, content relevance, and calculate a score
def check_page_quality(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Check if the request was successful

        # Parse the page content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find meta title and description
        title_tag = soup.find('title')
        title = title_tag.string if title_tag else ""
        meta_description = soup.find('meta', attrs={'name': 'description'})
        description = meta_description['content'] if meta_description else ""

        # Extract keywords from title and description
        title_keywords = extract_keywords(title)
        description_keywords = extract_keywords(description)
        relevant_keywords = title_keywords.union(description_keywords)

        # Extract and count the content on the page
        page_text = soup.get_text(separator=' ', strip=True)  # Get all visible text on the page
        word_count, content_keywords = count_words(page_text)

        # Content relevance based on keyword match
        content_relevance_keywords = relevant_keywords & content_keywords
        content_relevance_score = 100 * (len(content_relevance_keywords) / len(relevant_keywords)) if relevant_keywords else 100

        # Find all images and check for alt attributes
        images = soup.find_all('img')

        if not images:
            alt_score = 100  # No images, perfect score by default
            relevance_score = 100
        else:
            total_images = len(images)
            images_without_alt = sum(1 for img in images if not img.get('alt'))

            # Check alt attributes and calculate relevance
            relevant_alt_count = 0
            for img in images:
                alt_text = img.get('alt', "")
                alt_keywords = extract_keywords(alt_text)
                if relevant_keywords & alt_keywords:  # Check if there is a keyword match
                    relevant_alt_count += 1

            # Calculate the score for alt text presence
            alt_score = 100 * (1 - (images_without_alt / total_images)) if total_images > 0 else 100

            # Calculate the relevance score (percentage of relevant alt attributes)
            relevance_score = 100 * (relevant_alt_count / total_images) if total_images > 0 else 100

        # Final score is the average of the alt score, relevance score, and content relevance
        final_score = (alt_score + relevance_score + content_relevance_score) / 3

        return {
            "URL": url,
            "Score": round(final_score, 2),
            "Total Images": len(images),
            "Images Without Alt": images_without_alt if images else 0,
            "Alt Relevance Score": round(relevance_score, 2),
            "Content Word Count": word_count,
            "Content Relevance Score": round(content_relevance_score, 2)
        }

    except requests.exceptions.RequestException as e:
        return {"URL": url, "Score": "Error", "Total Images": "N/A", "Images Without Alt": "N/A", "Alt Relevance Score": "Error", "Content Word Count": "N/A", "Content Relevance Score": "Error", "Error": str(e)}

# Function to read URLs from a CSV file, check their content, image alt attributes, and write results to another CSV file
def check_urls_from_csv(input_csv, output_csv, max_workers=10):
    results = []

    # Open and read the input CSV file
    with open(input_csv, newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        url_list = [row[0] for row in reader]

    # Use ThreadPoolExecutor for multi-threaded URL processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_page_quality, url): url for url in url_list}

        # Collect the results as they complete
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Write the results to a new CSV file
    with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["URL", "Score", "Total Images", "Images Without Alt", "Alt Relevance Score", "Content Word Count", "Content Relevance Score"])
        writer.writeheader()

        # Write each result to the CSV file
        for result in results:
            writer.writerow(result)

    print(f"Results have been saved to {output_csv}")

# Example usage
input_csv = "url_list.csv"   # Input CSV file with URLs
output_csv = "page_quality_scores.csv"  # Output CSV file to store the results
max_workers = 10  # Number of threads to use

check_urls_from_csv(input_csv, output_csv, max_workers)
