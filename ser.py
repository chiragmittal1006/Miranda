import asyncio
import json
import os
import websockets
from google import genai
import base64
import io
from pydub import AudioSegment
import wave
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.gemini import Gemini
import shutil

os.environ['GOOGLE_API_KEY'] = ''
gemini_api_key = os.environ['GOOGLE_API_KEY']
MODEL = "gemini-2.0-flash-exp"
TRANSCRIPTION_MODEL = "gemini-1.5-flash-8b"
client = genai.Client(http_options={'api_version': 'v1alpha'})
gemini_embedding_model = GeminiEmbedding(api_key=gemini_api_key, model_name="models/text-embedding-004")
llm = Gemini(api_key=gemini_api_key, model_name="models/gemini-2.0-flash-exp")
Settings.llm = llm
Settings.embed_model = gemini_embedding_model

def build_index(doc_path="./downloads"):
    PERSIST_DIR = "./storage"
    if not os.path.exists(PERSIST_DIR):
        documents = SimpleDirectoryReader(doc_path).load_data()
        index = VectorStoreIndex.from_documents(documents)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
    return index

def query_docs(query):
    index = build_index()
    query_engine = index.as_query_engine()
    response = query_engine.query(query)
    return str(response)

tool_query_docs = {
    "function_declarations": [{
        "name": "query_docs",
        "description": "Query the document content with a specific query string.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING", "description": "The query string"}},
            "required": ["query"]
        }
    }]
}

async def gemini_session_handler(client_websocket):
    try:
        config_message = await client_websocket.recv()
        config_data = json.loads(config_message)
        config = config_data.get("setup", {})
        config["system_instruction"] = """You are a helpful assistant. Use the query_docs tool to answer questions based on uploaded documents when relevant."""
        config["tools"] = [tool_query_docs]

        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("Connected to Gemini API")
            session.audio_data = b''

            async def send_to_gemini():
                async for message in client_websocket:
                    data = json.loads(message)
                    if "realtime_input" in data:
                        for chunk in data["realtime_input"]["media_chunks"]:
                            if chunk["mime_type"] == "audio/pcm":
                                await session.send({"mime_type": "audio/pcm", "data": chunk["data"]})
                            elif chunk["mime_type"] == "image/jpeg":
                                await session.send({"mime_type": "image/jpeg", "data": chunk["data"]})
                            elif chunk["mime_type"] == "application/pdf":
                                pdf_data = base64.b64decode(chunk["data"])
                                filename = chunk.get("filename", "uploaded.pdf")
                                os.makedirs("./downloads", exist_ok=True)
                                file_path = os.path.join("./downloads", filename)
                                with open(file_path, "wb") as f:
                                    f.write(pdf_data)
                                if os.path.exists("./storage"):
                                    shutil.rmtree("./storage")
                                build_index()
                                await client_websocket.send(json.dumps({"text": f"PDF {filename} uploaded and indexed."}))
                            elif chunk["mime_type"] == "text/plain":
                                text = base64.b64decode(chunk["data"]).decode('utf-8')
                                await session.send({"mime_type": "text/plain", "data": text})

            async def receive_from_gemini():
                while True:
                    async for response in session.receive():
                        if response.server_content is None:
                            if response.tool_call:
                                function_calls = response.tool_call.function_calls
                                function_responses = []
                                for call in function_calls:
                                    if call.name == "query_docs":
                                        result = query_docs(call.args["query"])
                                        function_responses.append({"name": "query_docs", "response": {"result": result}, "id": call.id})
                                await session.send(input=function_responses)
                                continue
                            continue
                        model_turn = response.server_content.model_turn
                        if model_turn:
                            for part in model_turn.parts:
                                if hasattr(part, 'text') and part.text:
                                    await client_websocket.send(json.dumps({"text": part.text}))
                                elif hasattr(part, 'inline_data') and part.inline_data:
                                    base64_audio = base64.b64encode(part.inline_data.data).decode('utf-8')
                                    await client_websocket.send(json.dumps({"audio": base64_audio}))
                                    session.audio_data += part.inline_data.data
                        if response.server_content.turn_complete:
                            transcribed_text = transcribe_audio(session.audio_data)
                            if transcribed_text:
                                await client_websocket.send(json.dumps({"text": transcribed_text}))
                            session.audio_data = b''

            send_task = asyncio.create_task(send_to_gemini())
            receive_task = asyncio.create_task(receive_from_gemini())
            await asyncio.gather(send_task, receive_task)
    except Exception as e:
        print(f"Error in Gemini session: {e}")

def transcribe_audio(audio_data):
    if not audio_data:
        return "No audio data received."
    mp3_base64 = convert_pcm_to_mp3(audio_data)
    if not mp3_base64:
        return "Audio conversion failed."
    transcription_client = genai.GenerativeModel(model_name=TRANSCRIPTION_MODEL)
    response = transcription_client.generate_content([
        "Generate a transcript of the speech. If not recognizable, say '<Not recognizable>'.",
        {"mime_type": "audio/mp3", "data": base64.b64decode(mp3_base64)}
    ])
    return response.text

def convert_pcm_to_mp3(pcm_data):
    try:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(pcm_data)
        wav_buffer.seek(0)
        audio_segment = AudioSegment.from_wav(wav_buffer)
        mp3_buffer = io.BytesIO()
        audio_segment.export(mp3_buffer, format="mp3", codec="libmp3lame")
        return base64.b64encode(mp3_buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error converting PCM to MP3: {e}")
        return None

async def main():
    async with websockets.serve(gemini_session_handler, "localhost", 9085):
        print("Running websocket server localhost:9085...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())




# pip install -U google-genai==0.5.0 llama-index==0.12.11 llama-index-llms-gemini==0.4.3 llama-index-embeddings-gemini==0.3.1 websockets pydub


# Set API Key: Replace os.environ['GOOGLE_API_KEY'] = '' with your actual Google API key in server.py.
# Run the Backend: Execute python server.py.
# Serve the Frontend: Use a simple HTTP server (e.g., python -m http.server) in the directory containing index.html and pcm-processor.js, then open http://localhost:8000 in your browser.


# AIzaSyBMNn6dYVjTIqq9lq4dQwYseUXZrPg4nJ8