FROM ubuntu:24.04
RUN apt update && apt -y upgrade

# python deps
RUN apt install -y python3 python3-pip python3-virtualenv zip wget git
RUN mkdir ~/venv && cd ~/venv && virtualenv nlpdsse

####
RUN /bin/bash -c 'source ~/venv/nlpdsse/bin/activate && python3 -m pip install helics>=3.6.1 numpy>=2.4.2 oedisi~=3.0 pandas>=3.0.1 pytest>=9.0.2 pytest-cov>=7.0.0 requests>=2.32.5 flask>=3.1.3 casadi>=3.7.2 scipy>=1.17.1'

# install
COPY . /home/nlpdsse
RUN /bin/bash -c 'source ~/venv/nlpdsse/bin/activate && cd /home/nlpdsse/ && python3 -m pip install -e .'

ENTRYPOINT ["/bin/bash", "-c","source ~/venv/nlpdsse/bin/activate && python3 /home/nlpdsse/nlpdsse/microservice/server.py"]
