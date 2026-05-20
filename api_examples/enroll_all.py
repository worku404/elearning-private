import requests

username = 'gold'
token = 'ed5061fb83d1d48236b524add05e48fc6cca08b9'
headers = {
    'Authorization': f'Token {token}',
    'Accept': 'application/json',
}


base_url = 'http://127.0.0.1:8000/api/'
url = f'{base_url}courses/'

available_courses = []

while url is not None:
    print(f'Loading courses from {url}')
    r = requests.get(url, headers=headers)
    print('status:', r.status_code)
    response = r.json()
    url = response.get('next')
    courses = response.get('results',[])
    available_courses += [course['title'] for course in courses]
    
print (f'Available courses: {", ".join(available_courses)}')

for course in courses:
    course_id = course['id']
    course_title = course['title']
    r = requests.post(
        f'{base_url}courses/{course_id}/enroll/',
        headers=headers
    )
    
    if r.status_code==200:
        #successful request
        print(f'Successfully enrolled in {course_title}')