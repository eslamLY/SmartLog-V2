"""Helper functions for tests - import directly"""
import json

def login(client, eid='ADM001', pw='admin123'):
    return client.post('/login', data=json.dumps({'username': eid, 'password': pw}),
        content_type='application/json')

def logout(client):
    return client.get('/logout')
