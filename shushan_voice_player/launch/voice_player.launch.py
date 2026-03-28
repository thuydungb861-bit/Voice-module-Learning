from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='shushan_voice_player',
            executable='voice_player_node',
            name='voice_player',
            output='screen',
            parameters=[
                {
                    'topic_name': '/voice/text',
                    'sink_name': 'alsa_output.usb-Generic_USB2.0_Device_20170726905923-01.analog-stereo',
                }
            ],
        )
    ])
