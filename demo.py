# curl --request POST \
#   --data "code=4/1AVMBsJhXDsdUxAOgm-ZgG8wZxGjqn9o8KX_4989gF61j9FgqrqlTgjvhmOE" \
#   --data "client_id=23829735023-i1hh0alk7ubcgspp24iqim59815thai1.apps.googleusercontent.com" \
#   --data "client_secret=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" \ 
#   --data "redirect_uri=urn:ietf:wg:oauth:2.0:oob" \
#   --data "grant_type=authorization_code" \
#   https://oauth2.googleapis.com/token
#   refresh token= 1//0gjIZ_jtYT9qZCgYIARAAGBASNwF-L9IrnzWZNI4ZHGhiIRIscvFt26CbvOro44DgFPcLWOGv57sNyPugWQqcHm1Ld4B5JCDmwdw
import requests

data = {
    "code": "4/1AVMBsJhXDsdUxAOgm-ZgG8wZxGjqn9o8KX_4989gF61j9FgqrqlTgjvhmOE",
    "client_id": "23829735023-i1hh0alk7ubcgspp24iqim59815thai1.apps.googleusercontent.com",
    "client_secret": "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",
    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
    "grant_type": "authorization_code"
}

resp = requests.post("https://oauth2.googleapis.com/token", data=data)
print(resp.json())


