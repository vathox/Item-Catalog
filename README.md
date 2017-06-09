# Item-Catalog-Webb-App

## About


Application that provides a list of items within a variety of categories as well as provide a user registration and authentication system.
Registered users  have the ability to post, edit and delete their own items.


## In This Repo

This project has one main Python module itemCatalogProject.py which runs the Flask application. A SQL database is created using the database_setup.py. The Flask application uses stored HTML (ninja2) with Bootstrap4 templates in the tempaltes folder to build the front-end of the application.


## Runnig the app

1. Install Vagrant & VirtualBox
2. Clone the Udacity Vagrantfile
3. Go to Vagrant directory and clone this repo into it
4. Launch the Vagrant VM (`vagrant up`)
5. Log into Vagrant VM (`vagrant ssh`)
6. Navigate to cd/vagrant as instructed in terminal, you will need to intall requests module (`sudo pip install requests`)
7. Navigate to project directory
7. Run application  `python itemCatalogProject.py`
8.  Access the application locally using http://localhost:5000


 ## API endpoints: 

go to http://localhost:5000/catalog/json to get all the categories in database <br>
go to http://localhost:5000/CATEGORY_ID/json to get all items in a given category 
 
