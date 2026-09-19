"""WebSocket event schema for /ws/voice.

Client → server: audio_chunk {audio_b64, mime}, text_message {text}, interrupt, config {language_preference, conversation_id}
Server → client: state_change {state}, transcription {text}, user_message, assistant_text {text, language, model},
                 assistant_audio {audio_url}, error {message}
"""
