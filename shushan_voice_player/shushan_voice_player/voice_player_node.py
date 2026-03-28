import os
import queue
import shutil
import subprocess
import tempfile
import threading
from typing import List, Optional

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


class VoicePlayerNode(Node):
    def __init__(self) -> None:
        super().__init__('voice_player')

        self.declare_parameter('topic_name', '/voice/text')
        self.declare_parameter('audio_device', '')
        self.declare_parameter('sink_name', '')
        self.declare_parameter('tts_command', '')
        self.declare_parameter('player_command', '')
        self.declare_parameter('tts_voice', 'cmn')

        self.topic_name = self.get_parameter('topic_name').get_parameter_value().string_value
        self.audio_device = self.get_parameter('audio_device').get_parameter_value().string_value.strip()
        self.sink_name = self.get_parameter('sink_name').get_parameter_value().string_value.strip()
        self.tts_voice = self.get_parameter('tts_voice').get_parameter_value().string_value.strip()
        self.tts_command = self._resolve_command(
            self.get_parameter('tts_command').get_parameter_value().string_value.strip(),
            ['espeak-ng', 'espeak'],
        )
        self.player_command = self._resolve_command(
            self.get_parameter('player_command').get_parameter_value().string_value.strip(),
            ['paplay', 'aplay', 'ffplay'],
        )

        self.message_queue: "queue.Queue[str]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()  #循环从 message_queue 取字符串调用 TTS 程序合成语音调用播放器播放音频

        self.subscription = self.create_subscription(
            String,
            self.topic_name,
            self._on_message,
            10,
        )

        self.get_logger().info(f'Listening on topic: {self.topic_name}')
        self.get_logger().info(
            f'TTS command: {self.tts_command or "not found"}, '
            f'tts_voice: {self.tts_voice or "default"}, '
            f'player command: {self.player_command or "not found"}, '
            f'audio_device: {self.audio_device or "default"}, '
            f'sink_name: {self.sink_name or "default"}'
        )

    def destroy_node(self) -> bool:
        self.stop_event.set()
        self.message_queue.put('')
        if self.worker.is_alive():
            self.worker.join(timeout=2.0)
        return super().destroy_node()

    def _resolve_command(self, configured: str, candidates: List[str]) -> str:
        if configured:
            return configured
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return ''

    def _on_message(self, msg: String) -> None:
        payload = msg.data.strip()
        if not payload:
            self.get_logger().warning('Received empty voice message, skipping.')
            return

        self.get_logger().info(f'Received voice request: {payload}')
        self.message_queue.put(payload)

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                payload = self.message_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not payload:
                continue

            try:
                if os.path.isfile(payload):
                    self._play_file(payload)
                else:
                    self._speak_text(payload)
            except Exception as exc:  # pragma: no cover - defensive logging
                self.get_logger().error(f'Voice playback failed: {exc}')

    def _play_file(self, file_path: str) -> None:
        if not self.player_command:
            self.get_logger().error('No audio player found. Install aplay/ffplay/paplay.')
            return

        suffix = os.path.splitext(file_path)[1].lower()
        command: Optional[List[str]] = None

        if os.path.basename(self.player_command) == 'aplay':
            if suffix not in ('.wav', '.au'):
                self.get_logger().error('aplay only supports WAV/AU files. Please publish a .wav path.')
                return
            command = [self.player_command]
            if self.audio_device:
                command.extend(['-D', self.audio_device])
            command.append(file_path)
        elif os.path.basename(self.player_command) == 'ffplay':
            command = [self.player_command, '-nodisp', '-autoexit', '-loglevel', 'error', file_path]
        elif os.path.basename(self.player_command) == 'paplay':
            command = [self.player_command, file_path]

        if not command:
            self.get_logger().error('Could not construct audio playback command.')
            return

        subprocess.run(command, check=True, env=self._build_audio_env())

    def _build_audio_env(self) -> dict:
        env = os.environ.copy()
        if self.sink_name:
            env['PULSE_SINK'] = self.sink_name
        return env

    def _speak_text(self, text: str) -> None:
        if not self.tts_command:
            self.get_logger().error(
                'No TTS engine found. Install espeak-ng or publish a WAV file path instead.'
            )
            return

        tts_command = [self.tts_command]
        if self.tts_voice:
            tts_command.extend(['-v', self.tts_voice])
        tts_command.extend(['--stdout', text])

        tts_result = subprocess.run(
            tts_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if tts_result.returncode != 0:
            tts_error = tts_result.stderr.decode(errors='replace').strip()
            raise RuntimeError(f'TTS command failed: {tts_error or "unknown error"}')

        player_name = os.path.basename(self.player_command) if self.player_command else ''

        if player_name == 'aplay':
            play_command = [self.player_command]
            if self.audio_device:
                play_command.extend(['-D', self.audio_device])
            player_result = subprocess.run(
                play_command,
                input=tts_result.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                env=self._build_audio_env(),
            )
            if player_result.returncode != 0:
                player_error = player_result.stderr.decode(errors='replace').strip()
                raise RuntimeError(f'Audio player failed: {player_error or "unknown error"}')
            return

        if player_name == 'paplay':
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(tts_result.stdout)
                temp_wav_path = temp_file.name
            try:
                subprocess.run(
                    [self.player_command, temp_wav_path],
                    check=True,
                    env=self._build_audio_env(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            finally:
                if os.path.exists(temp_wav_path):
                    os.unlink(temp_wav_path)
            return

        subprocess.run([self.tts_command, text], check=True, env=self._build_audio_env())


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VoicePlayerNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
