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
        ],
    },
)
