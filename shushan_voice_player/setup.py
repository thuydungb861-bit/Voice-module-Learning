from setuptools import setup

package_name = 'shushan_voice_player'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/voice_player.launch.py']),
        ('share/' + package_name, ['README.md']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='wzz',
    maintainer_email='wzz@example.com',
    description='ROS 2 voice playback node for text or WAV path messages.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_player_node = shushan_voice_player.voice_player_node:main',
        ],
    },
)
