import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceHandler:
    def __init__(self):
        self._tts = None
        self._recognizer = None
        self._mic = None
        self.available = False
        self.listening = False
        self._init()

    def _init(self):
        try:
            import pyttsx3
            import speech_recognition as sr
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", 175)
            self._tts.setProperty("volume", 0.9)
            voices = self._tts.getProperty("voices")
            for v in voices:
                if any(x in v.name.lower() for x in ["female", "zira", "hazel", "susan"]):
                    self._tts.setProperty("voice", v.id)
                    break
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 3500
            self._recognizer.dynamic_energy_threshold = True
            self._mic = sr.Microphone()
            self.available = True
        except Exception as e:
            logger.warning(f"Voice unavailable: {e}")

    def speak(self, text: str):
        if not self.available:
            return
        def _run():
            try:
                self._tts.say(text)
                self._tts.runAndWait()
            except Exception as e:
                logger.error(f"TTS error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def listen(self, timeout: int = 5, limit: int = 15) -> Optional[str]:
        if not self.available:
            return None
        import speech_recognition as sr
        try:
            with self._mic as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.3)
                audio = self._recognizer.listen(src, timeout=timeout, phrase_time_limit=limit)
            return self._recognizer.recognize_google(audio)
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except Exception as e:
            logger.error(f"STT error: {e}")
            return None

    def start_continuous(self, callback: Callable, wake_word: str = "hey aria"):
        def _loop():
            self.listening = True
            while self.listening:
                text = self.listen(timeout=3)
                if text:
                    if wake_word.lower() in text.lower():
                        self.speak("Yes?")
                        cmd = self.listen(timeout=8)
                        if cmd:
                            callback(cmd)
                    else:
                        callback(text)
        threading.Thread(target=_loop, daemon=True).start()

    def stop(self):
        self.listening = False
