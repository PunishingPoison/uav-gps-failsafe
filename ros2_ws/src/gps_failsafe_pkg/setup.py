from setuptools import find_packages, setup

package_name = 'gps_failsafe_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='V C Mohit Rao',
    maintainer_email='187972426+PunishingPoison@users.noreply.github.com',
    description='Simulated failsafe architectures for GPS-denied UAV navigation and cyber-attack recovery.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'sensor_bridge_node = gps_failsafe_pkg.sensor_bridge_node:main',
            'mission_runner_node = gps_failsafe_pkg.mission_runner_node:main',
            'adversary_spoofer_node = gps_failsafe_pkg.adversary_spoofer_node:main',
            'telemetry_logger_node = gps_failsafe_pkg.telemetry_logger_node:main',
            'guardian_ai_node = gps_failsafe_pkg.guardian_ai_node:main',
        ],
    },
)
