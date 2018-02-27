# How to use the code with Docker

The Dockerfile is in the root directory. Run Docker from there.
The (cloned) source code is copied into the Docker image.

Before you do that, create the `siteprivate.py` file to the repository
directory (current directory). However, make sure you don't add it to
the repository.

Further, add parameter `host='0.0.0.0'` to the `app.run()` call
in `wps.py`. To avoid *Connection reset by peer* when accessing
the side from outside of the container.
Do not commit the `host='0.0.0.0'` change.

Finally, update the connection string in `wps.py`.

Build:

```
docker build -t wps-server .
```

Run:

```
docker run -it -p 5001:5000 --rm wps-server
```

Test:

http://localhost:5000/huc12_state

To connect to a database in Docker:

```
docker run -it --net ncthreats_default --link ncthreats_db_1:postgres -p 5000:5000 --rm wps-server
```
