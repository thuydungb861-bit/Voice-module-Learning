# shushan_voice_player

ROS 2 voice playback node for a USB speaker.

## Features

- Subscribe to `/voice/text` (`std_msgs/msg/String`)
- If the message is plain text, try to use `espeak-ng` or `espeak`
- If the message is an existing `.wav` file path, play it with `aplay`

## Build

```bash
cd /home/wzz/shushan_ros2
colcon build --packages-select shushan_voice_player
source install/setup.bash
```

## Run

```bash
ros2 launch shushan_voice_player voice_player.launch.py
```

## Publish text

```bash
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '你好'}"
```

## Publish a WAV path

```bash
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '/tmp/test.wav'}"
```

## Notes

- Current launch file uses `plughw:2,0`, which matches the USB speaker currently detected on this machine.
- Plain text playback needs `espeak-ng` or `espeak` to be installed.
- WAV playback works with the existing `aplay` command on this machine.
