import streamlit as st
import re
import json

# Placeholder for __app_id and __firebase_config, which are usually injected by the environment.
# These are not directly used in this standalone Streamlit app but are good practice to include
# if you were integrating with Firebase for persistence.
appId = "" # In a real Canvas environment, __app_id would be provided.
firebaseConfig = {} # In a real Canvas environment, __firebase_config would be provided.

# Function to call the Gemini API for text generation (summarization or quiz)
async def call_gemini_api(prompt, schema=None):
    """
    Calls the Gemini API to generate content based on the given prompt and schema.
    """
    chatHistory = []
    chatHistory.push({ "role": "user", "parts": [{ "text": prompt }] })

    payload = {
        "contents": chatHistory
    }

    if schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": schema
        }

    apiKey = "" # Canvas will provide this key at runtime.
    apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + apiKey

    try:
        response = await st.experimental_user.fetch(apiUrl, {
            "method": "POST",
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps(payload)
        })
        result = await response.json()

        if result.candidates and len(result.candidates) > 0 and \
           result.candidates[0].content and len(result.candidates[0].content.parts) > 0:
            text_response = result.candidates[0].content.parts[0].text
            if schema:
                return json.loads(text_response) # Parse JSON if a schema was provided
            else:
                return text_response
        else:
            st.error("Failed to get a valid response from the AI model. Please try again.")
            print(f"AI response error: {result}")
            return None
    except Exception as e:
        st.error(f"An error occurred while calling the AI model: {e}")
        return None

async def summarize_book(text_content, summary_length_ratio=0.3):
    """
    Summarizes the provided text content using the Gemini AI model.
    """
    prompt = f"Please summarize the following book text in a concise manner, aiming for about {int(summary_length_ratio*100)}% of the original length. Focus on the main plot, key characters, and significant events:\n\n{text_content[:8000]}" # Limit input to AI
    with st.spinner("Generating summary..."):
        summary = await call_gemini_api(prompt)
        return summary

def find_chapters(text_content):
    """
    Finds potential chapter headings in the text using common patterns.
    Returns a list of tuples (chapter_title, start_index, end_index).
    """
    chapters = []
    # Regex patterns for common chapter headings
    # This will capture "Chapter X", "CHAPTER X", "1. Title", "Chapter One", etc.
    chapter_patterns = [
        re.compile(r'^(Chapter\s+\d+|CHAPTER\s+\d+|Chapter\s+[IVXLCDM]+|Chapter\s+[A-Za-z]+|(\d+\.\s+)?\w+\s+.*)\s*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'^(Part\s+\d+|PART\s+\d+|Part\s+[IVXLCDM]+|Part\s+[A-Za-z]+)\s*$', re.MULTILINE | re.IGNORECASE)
    ]

    lines = text_content.split('\n')
    current_chapter_title = "Introduction/Beginning"
    current_chapter_start_index = 0

    for i, line in enumerate(lines):
        for pattern in chapter_patterns:
            if pattern.match(line.strip()):
                if current_chapter_title:
                    chapters.append({
                        "title": current_chapter_title.strip(),
                        "start_line": current_chapter_start_index,
                        "end_line": i - 1 # End previous chapter before current one starts
                    })
                current_chapter_title = line.strip()
                current_chapter_start_index = i
                break # Move to next line after finding a match

    # Add the last chapter
    if current_chapter_title:
        chapters.append({
            "title": current_chapter_title.strip(),
            "start_line": current_chapter_start_index,
            "end_line": len(lines) - 1
        })

    # Filter out empty chapters or very short "chapters" that are just section breaks
    chapters = [c for c in chapters if c["end_line"] >= c["start_line"]]

    return chapters

async def generate_book_quiz(text_segment):
    """
    Generates a multiple-choice quiz question from a given text segment
    using the Gemini AI model with a structured JSON response.
    """
    if not text_segment:
        return {"error": "Please provide text to generate a quiz."}

    # Define the JSON schema for the quiz question
    quiz_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "question": {"type": "STRING"},
                "options": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                },
                "correct_answer": {"type": "STRING"}
            },
            "required": ["question", "options", "correct_answer"]
        }
    }

    # Limit input to AI
    input_text_for_quiz = text_segment[:2000]

    prompt = f"""Generate one multiple-choice question from the following text.
    The question should have four options, and one correct answer.
    The correct answer must be one of the provided options.

    Text:
    {input_text_for_quiz}
    """

    with st.spinner("Generating quiz question..."):
        quiz_data = await call_gemini_api(prompt, schema=quiz_schema)
        return quiz_data

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="Book Assistant AI")

st.title("📚 Book Assistant AI")
st.markdown("Upload a text file of your book to get summaries, find chapters, and generate quizzes!")

# Sidebar for controls
with st.sidebar:
    st.header("Upload Book")
    uploaded_file = st.file_uploader("Choose a TXT file", type="txt")

# Main content area
if uploaded_file is not None:
    # Read the uploaded file
    text_content = uploaded_file.read().decode("utf-8")
    lines = text_content.split('\n')

    st.subheader("Book Content Preview")
    # Display first 2000 characters or less for preview
    st.text_area("Original Text (first 2000 chars)", text_content[:2000] + ("..." if len(text_content) > 2000 else ""), height=200, disabled=True)

    st.markdown("---")

    # --- Summarization Section ---
    st.header("📖 Book Summary")
    summary_length = st.slider("Select Summary Length (as % of original)", 10, 80, 30)
    if st.button("Generate Summary"):
        if text_content:
            summary = await summarize_book(text_content, summary_length / 100)
            if summary:
                st.subheader("Summary:")
                st.write(summary)
        else:
            st.warning("Please upload a book first.")

    st.markdown("---")

    # --- Chapter Finder Section ---
    st.header("🔖 Chapter Finder")
    chapters = find_chapters(text_content)

    if chapters:
        st.subheader("Found Chapters:")
        chapter_titles = [c["title"] for c in chapters]
        selected_chapter_title = st.selectbox("Select a Chapter to View", chapter_titles)

        if selected_chapter_title:
            selected_chapter_info = next((c for c in chapters if c["title"] == selected_chapter_title), None)
            if selected_chapter_info:
                start_line = selected_chapter_info["start_line"]
                end_line = selected_chapter_info["end_line"]
                chapter_text_lines = lines[start_line : end_line + 1]
                chapter_text = "\n".join(chapter_text_lines)
                st.text_area(f"Content of '{selected_chapter_title}'", chapter_text[:5000] + ("..." if len(chapter_text) > 5000 else ""), height=300)

                # --- Quiz Generation Section for Selected Chapter ---
                st.subheader("❓ Generate Quiz from Selected Chapter")
                if st.button(f"Generate Quiz for '{selected_chapter_title}'"):
                    if chapter_text:
                        quiz_result = await generate_book_quiz(chapter_text)
                        if quiz_result and isinstance(quiz_result, list) and quiz_result:
                            st.subheader("Generated Quiz Question:")
                            for q_data in quiz_result:
                                st.write(f"**Question:** {q_data['question']}")
                                for i, option in enumerate(q_data['options']):
                                    st.write(f"  {chr(65 + i)}. {option}")
                                st.write(f"**Correct Answer:** {q_data['correct_answer']}")
                        elif "error" in quiz_result:
                            st.error(quiz_result["error"])
                        else:
                            st.warning("Could not generate quiz. The AI might not have found enough context or the response was not structured as expected.")
                    else:
                        st.warning("No text available for the selected chapter to generate a quiz.")
    else:
        st.info("No chapters found. Chapter detection works best with clear headings like 'Chapter 1', 'CHAPTER TWO', 'Part 1', etc.")

    st.markdown("---")


else:
    st.info("Please upload a book (TXT file) to get started!")