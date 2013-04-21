# Escape from `/dev/null`
## Google Stockholm - 2013-04-20

This is our (@vals, @brainstorm) repository for the 'Escape from `/dev/null`' competition at Google Stockholm.

The text for the challanges we made it to can be viewed, along with some challange specific experimentation
can be found in this IPython notebook:

  http://nbviewer.ipython.org/urls/raw.github.com/vals/google_devnull/master/Google%2520devnull.ipynb
  
Most of the code implemented is in the file `devnull_srv.py`.

At the end, this is what our interface looked like

![devnull](https://raw.github.com/vals/google_devnull/master/Screen%20Shot%202013-04-20%20at%2021.04.43.png)

#### Points is pride:

- Redis in the backend for rate limiting requests
- Minimal code for the API using Flask
- Maps created with NumPy and matplotlib
