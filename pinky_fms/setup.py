from setuptools import setup

package_name = 'pinky_fms'
setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CAS project',
    maintainer_email='fms@example.invalid',
    description='Central FMS/Nav2 action worker',
    license='TODO (license to be selected by repository owner)',
    entry_points={'console_scripts': ['worker = pinky_fms.worker:main']},
)
