# Adds python3 to ejabberd/ecs so the external-auth "yes-man" script can run.
# python3 because Alpine ships it small (~30MB) and binary stdin handling is
# more reliable than bash for the length-prefixed ejabberd extauth protocol.
FROM ejabberd/ecs:latest

USER root
RUN apk add --no-cache python3 \
    && ln -sf /usr/bin/python3 /usr/local/bin/python3
USER ejabberd
