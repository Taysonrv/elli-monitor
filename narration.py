"""Narração local com vozes SAPI instaladas no Windows."""
import base64
import json
import os
import subprocess
import threading

BUSY = threading.Lock()
SCRIPT = r'''
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Speech
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload.text))
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voice = $synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'pt-*' } | Select-Object -First 1
    if (-not $voice) { Write-Output 'NO_PT_VOICE'; exit 2 }
    $synth.SelectVoice($voice.VoiceInfo.Name)
    $synth.Rate = 1
    $stream = New-Object IO.MemoryStream
    $synth.SetOutputToWaveStream($stream)
    $synth.Speak($text)
    $synth.SetOutputToNull()
    [Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))
    $stream.Dispose()
    $synth.Dispose()
} catch { Write-Output 'SPEECH_FAILED'; exit 3 }
'''


def synthesize(text):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 700:
        raise ValueError('Escreva uma narração de 1 a 700 caracteres.')
    if os.name != 'nt':
        raise ValueError('A voz automática local requer Windows. Use um arquivo de narração no painel.')
    if not BUSY.acquire(blocking=False):
        raise ValueError('Uma narração já está sendo preparada. Aguarde.')
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
             base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')],
            input=json.dumps({'text': base64.b64encode(text.encode('utf-8')).decode('ascii')}),
            capture_output=True, text=True, encoding='ascii', errors='replace', timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if 'NO_PT_VOICE' in result.stdout:
            raise ValueError('Não há voz em português disponível no Windows para este motor. Instale uma voz compatível ou envie sua narração em áudio.')
        if result.returncode:
            raise ValueError('O motor de voz do Windows falhou. Envie sua narração em áudio ou confira as vozes instaladas.')
        encoded = result.stdout.strip()
        try:
            audio = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise ValueError('O motor de voz retornou áudio inválido.') from None
        if not audio.startswith(b'RIFF') or len(audio) < 44:
            raise ValueError('O motor de voz não gerou um arquivo WAV válido.')
        return {'audio': encoded, 'mime': 'audio/wav'}
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Não foi possível preparar a voz local. Tente novamente ou envie um arquivo de narração.') from None
    finally:
        BUSY.release()
