FROM python:3

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./requirements.txt /app
COPY ./realtime_downloader.py /app
COPY ./data_types /app/data_types

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run realtime_downloader.py when the container launches
CMD ["python", "realtime_downloader.py"]
