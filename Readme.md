# Abe Importer

## Pycroft instance preparation
You should navigate to your pycroft directory and check out the `abe_importer_prep` branch.

On the pg-cluster:
```shell script
sudo -u postgres pg_dump -Fc -c --if-exists -n pycroft usermanagement > userman_pycroft.dump
```
Copy on your local machine and restore the dump:
```shell script
scp pg-cluster0.agdsn.network:userman_pycroft.dump pycroft_for_abe_importer.sql
drc stop dev-app
./restore_dump.sh  # do this before every import execution
```

The password get asked for is, of course, `password`.

## Set up 
First, set up a tunnel to the pg-User
cluster (assuming you have access to the 
`abe_importer` password or an equivalent account):

```shell script
ssh -NL 15432:pg-cluster0.agdsn.network:5432 login.agdsn.tu-dresden.de 
```

Then, insert the `postgres` URI in the `.abe_uri` file:

```shell script
echo -n "abe_importer password: "; read -s pw 
echo "postgres://abe_importer:$pw@localhost:15432/"\
"usermanagement?options=-csearch_path%3Dabe" > .abe_uri
``` 


Now, install the dependencies with [pipenv](https://pipenv.readthedocs.io/en/latest/):

```shell script
pipenv install --dev  # this may take a while
pipenv shell  # putting you in the virtualenv
``` 

There, you can manually do stuff using `ipython` (but you have to set the session manually)
or just run

```shell script
abe_importer -v
```
