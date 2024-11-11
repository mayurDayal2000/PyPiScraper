# use official python runtime as a parent image
FROM python:3.9

# set the working directory in the container
WORKDIR /PyPiScraper

# copy the requirements file into the container
COPY requirements.txt .

# install the packages
RUN pip install --no-cache-dir -r requirements.txt

# copy rest of the application code into the container
COPY . .

# run the application
CMD ["python", "main.py"]