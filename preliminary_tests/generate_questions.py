import os
import csv
import requests
import json
from pathlib import Path

# Ollama API endpoint (runs locally on your Mac)
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Model to use - make sure to run: ollama pull mistral
# Other options: llama2, neural-chat, orca-mini
MODEL_NAME = "mistral"

# Define input and output paths
INPUT_FOLDER = "input_for_q"
OUTPUT_FOLDER = "output_for_q"

# Create output folder if it doesn't exist
Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

# Function to generate an information-seeking question from extracted text
def generate_question(extracted_text):
    """
    Uses Ollama API to generate an information-seeking question based on extracted text.
    Ollama runs locally on your Mac - no external API calls or quotas!
    
    Args:
        extracted_text: The text snippet to generate a question from
    
    Returns:
        A question string, or error message if generation fails
    """
    try:
        # Create a prompt that instructs the model to generate a question
        prompt = f"""Based on the following text excerpt, generate a single, clear information-seeking question 
that a reader might ask after reading this text. The question should be specific and encourage deeper understanding 
of the topic. Keep the question concise (under 20 words).

Text: {extracted_text}

Question:"""
        
        # Call the Ollama API running locally
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False  # Wait for complete response
            },
            timeout=60  # Give it time to process
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("response"):
                # Clean up the response
                question = result["response"].strip()
                # Remove leading "Question:" if the model included it
                if question.lower().startswith("question:"):
                    question = question[9:].strip()
                return question
            else:
                return "Failed to generate question"
        else:
            return f"Error: API returned status {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure Ollama is running (ollama serve)"
    except Exception as e:
        # Handle any other errors gracefully
        print(f"  ✗ Error generating question: {str(e)}")
        return f"Error: {str(e)}"

# Process each input file
input_files = list(Path(INPUT_FOLDER).glob("*.csv"))
print(f"📚 Found {len(input_files)} input files to process\n")

for input_file in sorted(input_files):
    input_filename = input_file.name
    print(f"🔄 Processing: {input_filename}")
    
    # Generate output filename: input_filename_q.csv
    # e.g., "first_100 - first_100.csv" becomes "first_100 - first_100_q.csv"
    output_filename = input_filename.replace(".csv", "_q.csv")
    output_path = Path(OUTPUT_FOLDER) / output_filename
    
    try:
        # Open the input CSV file for reading
        with open(input_file, "r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            
            # Get the field names from the input file
            fieldnames = reader.fieldnames
            
            # Add "question" as a new column
            output_fieldnames = fieldnames + ["question"]
            
            # Open the output CSV file for writing
            with open(output_path, "w", newline="", encoding="utf-8") as outfile:
                writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
                
                # Write the header row
                writer.writeheader()
                
                # Process each row in the input file
                row_count = 0
                for row in reader:
                    row_count += 1
                    
                    # Extract the text from the "extracted_text" column
                    extracted_text = row.get("extracted_text", "")
                    
                    if extracted_text:
                        # Generate a question based on the extracted text
                        question = generate_question(extracted_text)
                        print(f"  ✓ Row {row_count}: Generated question for '{row.get('article_title', 'Unknown')}'")
                    else:
                        # If no extracted text, set question to empty
                        question = "No text provided"
                        print(f"  ⚠️  Row {row_count}: No extracted text found")
                    
                    # Add the generated question to the row
                    row["question"] = question
                    
                    # Write the row to the output file
                    writer.writerow(row)
        
        print(f"  ✓ Completed: {output_filename} ({row_count} rows processed)\n")
        
    except Exception as e:
        print(f"  ✗ Error processing file: {str(e)}\n")

print(f"✅ All files processed!")
print(f"📁 Output files saved to: {OUTPUT_FOLDER}/")
