import requests

def list_ollama_models():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json()
            print("\nAvailable Ollama Models:")
            print("-----------------------")
            for model in models['models']:
                print(f"Name: {model['name']}")
                print(f"Size: {model['size']}")
                print(f"Modified: {model['modified']}")
                print("-----------------------")
        else:
            print(f"Error: Status code {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Ollama. Make sure Ollama is running (ollama serve)")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    list_ollama_models()