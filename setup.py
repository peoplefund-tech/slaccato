from setuptools import setup, find_packages


setup(name='slaccato',
      version='0.2.1',
      description='Structured Slack bot framework.',
      long_description=open('README.md').read(),
      long_description_content_type="text/markdown",
      license='MIT',
      author='Dongho Yu',
      author_email='n0rr7882@gmail.com',
      url='https://github.com/peoplefund-tech/slaccato',
      install_requires=['certifi==2022.12.7',
                        'chardet==3.0.4',
                        'idna==2.7',
                        'requests>=2.19.1',
                        'six==1.11.0',
                        'slackclient==1.3.0',
                        'urllib3==1.24.2',
                        'websocket-client==0.53.0'],
      packages=find_packages(exclude=['slack_methods']),
      python_requires='>=3.4',
      classifiers=[
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
      ])
