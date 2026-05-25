import os
import requests
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator

PISTON_API_URL = os.getenv('PISTON_API_URL', 'http://piston:2000/api/v2/execute')

# Maps frontend language names → (piston language, version, file extension)
LANGUAGE_CONFIG = {
    'python':      ('python',     '3.12.0',  'main.py'),
    'javascript':  ('javascript', '20.11.1', 'main.js'),
    'js':          ('javascript', '20.11.1', 'main.js'),
    'c++':         ('c++',        '10.2.0',  'main.cpp'),
    'cpp':         ('c++',        '10.2.0',  'main.cpp'),
    'sqlite':      ('sqlite3',    '3.36.0',  'main.sql'),
    'sql':         ('sqlite3',    '3.36.0',  'main.sql'),
    'language-cpp':('c++',        '10.2.0',  'main.cpp'),  # fallback if JS sends raw class
    'sqlite3':      ('sqlite3',    '3.36.0',  'main.sql'),  # Prevents KeyError crashes from frontend selection
}


@method_decorator(csrf_exempt, name='dispatch')
class ExecuteCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code     = request.data.get('code', '').strip()
        language = request.data.get('language', 'python').lower().strip()

        if not code:
            return Response({'error': 'Code is required'}, status=status.HTTP_400_BAD_REQUEST)

        config = LANGUAGE_CONFIG.get(language)
        if not config:
            return Response(
                {'error': f'Unsupported language: "{language}". Supported: python, javascript, c++, sqlite3'},
                status=status.HTTP_400_BAD_REQUEST
            )

        piston_language, piston_version, filename = config

        payload = {
            "language": piston_language,
            "version":  piston_version,
            "files":    [{"name": filename, "content": code}],
            "stdin":    "",
            "args":     [],
            "compile_timeout": 10000,
            "run_timeout":     3000,
        }

        try:
            response = requests.post(PISTON_API_URL, json=payload, timeout=15)

            # Surface Piston errors clearly instead of raising a generic HTTPError
            if not response.ok:
                try:
                    piston_msg = response.json().get('message', response.text)
                except Exception:
                    piston_msg = response.text
                return Response(
                    {'error': f'Execution engine error: {piston_msg}'},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            data = response.json()
            run            = data.get('run', {})
            compile_result = data.get('compile', {})

            return Response({
                'stdout':   run.get('stdout', ''),
                'stderr':   run.get('stderr', '') or compile_result.get('stderr', ''),
                'exit_code': run.get('code', 0),
                'language': piston_language,
                'version':  piston_version,
            })

        except requests.exceptions.Timeout:
            return Response({'error': 'Code execution timed out'}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.exceptions.ConnectionError:
            return Response({'error': 'Could not connect to code execution engine'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)