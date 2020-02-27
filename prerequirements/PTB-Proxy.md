# Behind the PTB web Proxy

So are you working inside the PTB's network? Are you having nightmares with the proxy settings? This guidelines can help you to configure your machine before installing Hyperledger Fabric.

Only for the record, the PTB's proxy in Berlin is <http://webproxy.berlin.ptb.de:8080>.

## General concerns

Follow this [tutorial](https://www.serverlab.ca/tutorials/linux/administration-linux/how-to-configure-proxy-on-ubuntu-18-04/) if you need some general help and guidelines to do the following actions:

* Configure system proxy (e.g., /etc/environment);
* Configure apt-get proxy;

## Configure the curl

You will need *curl* to download all the Fabric tools and its docker images. You can use the this [link](https://stackoverflow.com/questions/7559103/how-to-setup-curl-to-permanently-use-a-proxy) to configure the *curl* proxy settings.

## Configure snap

The tool *snap* is necessary to work with Golang dependencies. You can find instructions about how to config *snap* proxy [here](https://askubuntu.com/questions/764610/how-to-install-snap-packages-behind-web-proxy-on-ubuntu-16-04).

## Configure docker

Docker containers also requires a proper proxy configuration. Please check this [tutorial](https://stackoverflow.com/questions/23111631/cannot-download-docker-images-behind-a-proxy) if you need a help to do that.

## Configure pip3

I could not find how to define *pip3* proxy settings permanently. But you can work around by using the *--proxy* parameter in the *pip3* command line, just like showed below. IMPORTANT: _you do not need execute this command now_. You only need to remember it when you are working with pip3.

```console
pip3 install --proxy http://webproxy.berlin.ptb.de:8080 -U cryptography
```