import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import boto3
import base64
import datetime

# Configure models with their required parameters
MODELS = {
    "Chat": [
        {"name": "Amazon Titan Text G1 - Express", "modelId": "amazon.titan-text-express-v1"},
        {"name": "Meta Llama 3 70B Instruct", "modelId": "meta.llama3-70b-instruct-v1:0"},
        {"name": "Mistral Mixtral 8x7B", "modelId": "mistral.mixtral-8x7b-instruct-v0:1"},
        {"name": "Cohere Command R", "modelId": "cohere.command-r-v1:0"},
        # {"name": "AI21 Jamba", "modelId": "ai21.jamba-1-5-large-v1:0"}
    ],
    "Image": [
        {"name": "Stable Diffusion XL", "modelId": "stability.stable-diffusion-xl-v1"},
        {"name": "Amazon Titan Image Generator", "modelId": "amazon.titan-image-generator-v2:0"}
    ],
    # "Video": [
    #     {"name": "Amazon Nova Reel", "modelId": "amazon.nova-reel-v1"}
    # ]
}

# Initialize AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime")

def create_unique_file(file_name, directory):
    """Create a file with a unique name by appending numbers if needed"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    base_name, extension = os.path.splitext(file_name)
    file_path = os.path.join(directory, file_name)
    i = 1
    
    while os.path.exists(file_path):
        file_name = f"{base_name}_{i}{extension}"
        file_path = os.path.join(directory, file_name)
        i += 1
    
    return file_path

def clear_output():
    """Clear the output text area"""
    output_text.delete('1.0', tk.END)
    
def sanitize_filename(filename):
    """Replace invalid filename characters with underscores"""
    invalid_chars = '<>:"/\\|?*:'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def make_api_request():
    model_type = model_type_var.get()
    selected_model = model_var.get()
    model_info = next((m for m in MODELS[model_type] if m["name"] == selected_model), None)
    
    if not model_info:
        output_text.insert(tk.END, "Invalid model selection.\n")
        return
    
    model_id = model_info["modelId"]
    prompt = prompt_entry.get("1.0", tk.END).strip()

    if not prompt:
        output_text.insert(tk.END, "Please enter a prompt.\n")
        return
    
    try:
        # Format the request body according to the specific model
        if model_id == "amazon.titan-text-express-v1":
            body = json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 8192,
                    "stopSequences": [],
                    "temperature": 0.7,
                    "topP": 0.9
                }
            })
        elif model_id == "meta.llama3-70b-instruct-v1:0":
            body = json.dumps({
                "prompt": prompt,
                "max_gen_len": 512,
                "temperature": 0.5,
                "top_p": 0.9
            })
        elif model_id == "mistral.mixtral-8x7b-instruct-v0:1":
            body = json.dumps({
                "prompt": f"<s>[INST] {prompt} [/INST]",
                "max_tokens": 512,
                "temperature": 0.5,
                "top_p": 0.9
            })
        elif model_id == "cohere.command-r-v1:0":
            body = json.dumps({
                "message": prompt,
                "chat_history": [],
                "max_tokens": 512,
                "temperature": 0.5
            })
        elif model_id == "ai21.jamba-1-5-large-v1:0":
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": prompt
                }],
                "max_tokens": 1000,
                "temperature": 0.7,
                "top_p": 0.9
            })
        elif model_id == "stability.stable-diffusion-xl-v1":
            body = json.dumps({
                "text_prompts": [{"text": prompt, "weight": 1}],
                "cfg_scale": 10,
                "seed": 0,
                "steps": 50,
                "width": 512,
                "height": 512
            })
        elif model_id == "amazon.titan-image-generator-v2:0":
            body = json.dumps({
                "textToImageParams": {"text": prompt},
                "taskType": "TEXT_IMAGE",
                "imageGenerationConfig": {
                    "cfgScale": 8,
                    "seed": 42,
                    "quality": "standard",
                    "width": 1024,
                    "height": 1024,
                    "numberOfImages": 1
                }
            })
        elif model_id == "amazon.nova-reel-v1":
            messagebox.showinfo("Video Generation", "Video generation requires S3 configuration. Please implement S3 bucket settings.")
            return
        
        # Make the API request
        response = bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        
        # Process the response
        if model_type == "Chat":
            if model_id == "amazon.titan-text-express-v1":
                output_text.insert(tk.END, response_body.get("results", [{}])[0].get("outputText", "No response") + "\n")
            elif model_id == "meta.llama3-70b-instruct-v1:0":
                output_text.insert(tk.END, response_body.get("generation", "No response") + "\n")
            elif model_id == "mistral.mixtral-8x7b-instruct-v0:1":
                output_text.insert(tk.END, response_body.get("outputs", [{}])[0].get("text", "No response") + "\n")
            elif model_id == "cohere.command-r-v1:0":
                output_text.insert(tk.END, response_body.get("text", "No response") + "\n")
            elif model_id == "ai21.jamba-1-5-large-v1:0":
                output_text.insert(tk.END, response_body.get("outputs", [{}])[0].get("text", "No response") + "\n")
        
        elif model_type == "Image":
            try:
                if model_id == "stability.stable-diffusion-xl-v1":
                    image_bytes = base64.b64decode(response_body["artifacts"][0]["base64"])
                elif model_id == "amazon.titan-image-generator-v2:0":
                    # Titan returns a list of base64-encoded images
                    if "images" in response_body and len(response_body["images"]) > 0:
                        image_data = response_body["images"][0]
                        # Some Titan responses include a prefix we need to remove
                        if "," in image_data:
                            image_data = image_data.split(",")[1]
                        image_bytes = base64.b64decode(image_data)
                    else:
                        raise ValueError("No image data found in response")
                
                output_dir = "generated_images"
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                model_name = sanitize_filename(model_id.split('.')[-1])
                base_filename = f"{model_name}_{timestamp}.png"
                
                # Create unique filename
                file_path = create_unique_file(base_filename, output_dir)
                
                # Write the image file
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                
                # Verify the file was written
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    output_text.insert(tk.END, f"✔ Image successfully saved:\n")
                    output_text.insert(tk.END, f"  File: {os.path.basename(file_path)}\n")
                    output_text.insert(tk.END, f"  Size: {os.path.getsize(file_path)} bytes\n")
                    output_text.insert(tk.END, f"  Path: {os.path.abspath(file_path)}\n\n")
                    
                    # Make the path clickable (Windows only)
                    if os.name == 'nt':
                        output_text.tag_config("path", foreground="blue", underline=1)
                        output_text.insert(tk.END, "Click here to open folder", "path")
                        output_text.tag_bind("path", "<Button-1>", 
                                        lambda e: os.startfile(os.path.abspath(output_dir)))
                else:
                    output_text.insert(tk.END, "❌ Error: File was not created properly\n")
                    
            except Exception as img_error:
                messagebox.showerror("Image Error", f"Failed to process image: {str(img_error)}")
                output_text.insert(tk.END, f"Image processing error: {str(img_error)}\n")
        
    except Exception as e:
        messagebox.showerror("API Error", f"Request failed: {str(e)}")
        output_text.insert(tk.END, f"Error: {str(e)}\n")

# Create main window
root = tk.Tk()
root.title("AWS Bedrock Model Interface")

# Model Type Selection
model_type_var = tk.StringVar(value="Chat")
tk.Label(root, text="Select Model Type:").pack()
type_dropdown = ttk.Combobox(root, textvariable=model_type_var, values=list(MODELS.keys()), state="readonly")
type_dropdown.pack()

def update_model_dropdown(*args):
    models = [m["name"] for m in MODELS[model_type_var.get()]]
    model_dropdown["values"] = models
    if models:
        model_var.set(models[0])

model_type_var.trace_add("write", update_model_dropdown)

# Model Selection
model_var = tk.StringVar()
tk.Label(root, text="Select Model:").pack()
model_dropdown = ttk.Combobox(root, textvariable=model_var, state="readonly")
model_dropdown.pack()
update_model_dropdown()

# Prompt Entry
tk.Label(root, text="Enter Prompt:").pack()
prompt_entry = scrolledtext.ScrolledText(root, height=5, width=50)
prompt_entry.pack()

# Button Frame
button_frame = tk.Frame(root)
button_frame.pack(pady=5)

# Generate Button
generate_btn = tk.Button(button_frame, text="Generate", command=make_api_request)
generate_btn.pack(side=tk.LEFT, padx=5)

# Clear Output Button
clear_btn = tk.Button(button_frame, text="Clear Output", command=clear_output)
clear_btn.pack(side=tk.LEFT, padx=5)

# Output Display
tk.Label(root, text="Output:").pack()
output_text = scrolledtext.ScrolledText(root, height=10, width=50)
output_text.pack()

# Run Application
root.mainloop()