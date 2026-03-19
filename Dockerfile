FROM ubuntu:24.04
RUN apt update && apt -y upgrade

# python deps
RUN apt install -y python3 python3-pip python3-virtualenv zip wget git
RUN mkdir ~/venv && cd ~/venv && virtualenv nlpdsse

# install
COPY . /home/nlpdsse
RUN /bin/bash -c 'source ~/venv/nlpdsse/bin/activate && cd /home/nlpdsse/ && python3 -m pip install -e .'

ENTRYPOINT ["/bin/bash", "-c","source ~/venv/nlpdsse/bin/activate && python3 /home/nlpdsse/nlpdsse/microservice/server.py"]
