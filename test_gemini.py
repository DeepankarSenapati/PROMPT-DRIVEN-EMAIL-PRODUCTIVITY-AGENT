from llm_client import call_gemini_text

def main():
    prompt = "Say hello in five words."
    print("Sending prompt to Gemini:", prompt)

    try:
        resp = call_gemini_text(prompt)
        print("\n=== MODEL OUTPUT ===\n")
        print(resp)
        print("\n=== END OUTPUT ===\n")
    except Exception as e:
        print("Error calling Gemini:", repr(e))
        raise

if __name__ == "__main__":
    main()
