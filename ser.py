import asyncio
import json
import os
import websockets
import base64
import io
from pydub import AudioSegment
import google.generativeai as generative
import google.generativeai.generative_models as generative_models
import wave

# Load API key from environment
os.environ['GOOGLE_API_KEY'] = ''
generative.configure(api_key=os.environ['GOOGLE_API_KEY'])
MODEL = "gemini-2.0-flash-exp"  # use your model ID
TRANSCRIPTION_MODEL = "gemini-1.5-flash-8b"

async def gemini_session_handler(client_websocket: websockets.WebSocketServerProtocol):
    """Handles the interaction with Gemini API within a websocket session."""
    try:
        config_message = await client_websocket.recv()
        config_data = json.loads(config_message)
        config = config_data.get("setup", {})
        generation_config = config.get("generation_config")

        # Initialize the Gemini model with the generation_config
        gemini_model = generative_models.GenerativeModel(model_name=MODEL, generation_config=generation_config)

        chat_session = gemini_model.start_chat()  # Start the chat session

        print("Connected to Gemini API")

        async def send_to_gemini():
            """Sends messages from the client websocket to the Gemini API."""
            try:
                async for message in client_websocket:
                    try:
                        data = json.loads(message)
                        if "realtime_input" in data:
                            for chunk in data["realtime_input"]["media_chunks"]:
                                if chunk["mime_type"] == "audio/pcm":
                                    await chat_session.send_message([{"mime_type": "audio/pcm", "data": base64.b64decode(chunk["data"])}])

                                elif chunk["mime_type"] == "image/jpeg":
                                    await chat_session.send_message([{"mime_type": "image/jpeg", "data": base64.b64decode(chunk["data"])}])

                    except Exception as e:
                        print(f"Error sending to Gemini: {e}")
                print("Client connection closed (send)")
            except Exception as e:
                print(f"Error sending to Gemini: {e}")
            finally:
                print("send_to_gemini closed")

        async def receive_from_gemini():
            """Receives responses from the Gemini API and forwards them to the client, looping until turn is complete."""
            try:
                while True:
                    try:
                        print("receiving from gemini")
                        response = await chat_session.send_message("") # Trigger a response based on prior context
                        if response and response.parts:
                            for part in response.parts:
                                if hasattr(part, 'text') and part.text is not None:
                                    await client_websocket.send(json.dumps({"text": part.text}))
                                elif hasattr(part, 'inline_data') and part.inline_data is not None:
                                    print("audio mime_type:", part.inline_data.mime_type)
                                    base64_audio = base64.b64encode(part.inline_data.data).decode('utf-8')
                                    await client_websocket.send(json.dumps({"audio": base64_audio}))
                                    # Accumulate audio data (if needed - consider if transcription needs full audio)
                                    if not hasattr(chat_session, 'audio_data'):
                                        chat_session.audio_data = b''
                                    chat_session.audio_data += part.inline_data.data
                                    print("audio received")

                        if response and response.is_end_of_stream:
                            print('\n<Turn complete>')
                            if hasattr(chat_session, 'audio_data'):
                                transcribed_text = await transcribe_audio(chat_session.audio_data)
                                if transcribed_text:
                                    await client_websocket.send(json.dumps({
                                        "text": transcribed_text
                                    }))
                                del chat_session.audio_data # Clear accumulated audio
                            break # End of the turn for the model

                    except websockets.exceptions.ConnectionClosedOK:
                        print("Client connection closed normally (receive)")
                        break
                    except Exception as e:
                        print(f"Error receiving from Gemini: {e}")
                        break

            except Exception as e:
                print(f"Error receiving from Gemini: {e}")
            finally:
                print("Gemini connection closed (receive)")

        # Start send and receive tasks
        send_task = asyncio.create_task(send_to_gemini())
        receive_task = asyncio.create_task(receive_from_gemini())
        await asyncio.gather(send_task, receive_task)

    except Exception as e:
        print(f"Error in Gemini session: {e}")
    finally:
        print("Gemini session closed.")

async def transcribe_audio(audio_data: bytes) -> str | None:
    """Transcribes audio using Gemini 1.5 Flash."""
    try:
        if not audio_data:
            return "<Not recognizable>"

        mp3_audio_base64 = convert_pcm_to_mp3(audio_data)
        if not mp3_audio_base64:
            return "<Not recognizable>"

        transcription_model = generative_models.GenerativeModel(model_name=TRANSCRIPTION_MODEL)

        prompt = """Generate a transcript of the speech.
        Please do not include any other text in the response.
        If you cannot hear the speech, please only say '<Not recognizable>'."""

        response = await transcription_model.generate_content(
            [
                prompt,
                {
                    "mime_type": "audio/mp3",
                    "data": base64.b64decode(mp3_audio_base64),
                }
            ]
        )

        if response.text:
            return response.text.strip()
        else:
            return "<Not recognizable>"

    except Exception as e:
        print(f"Transcription error: {e}")
        return "<Not recognizable>"

def convert_pcm_to_mp3(pcm_data: bytes) -> str | None:
    """Converts PCM audio to base64 encoded MP3."""
    try:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        audio_segment = AudioSegment.from_wav(wav_buffer)
        mp3_buffer = io.BytesIO()
        audio_segment.export(mp3_buffer, format="mp3", codec="libmp3lame")
        mp3_base64 = base64.b64encode(mp3_buffer.getvalue()).decode('utf-8')
        return mp3_base64

    except Exception as e:
        print(f"Error converting PCM to MP3: {e}")
        return None

async def main() -> None:
    async with websockets.serve(gemini_session_handler, "localhost", 9083):
        print("Running websocket server localhost:9083...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())