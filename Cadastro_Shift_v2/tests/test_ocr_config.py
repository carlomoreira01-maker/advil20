"""Configuração OCR, instalação e documentos inteiramente fictícios."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from ocr_runtime import (ROOT, candidate_executables, tesseract_exe, save_settings, load_settings,
                         settings_file, ocr_configuration, check_ocr_health, run_local)
from engine_v2 import read_document, parse_document, catalog_load
from test_v2 import TEXT, scan_image


class OCRConfiguravel(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='OCR configuração ')
        self.base=Path(self.tmp.name);self.config=self.base/'config.json'
        self.real=tesseract_exe()

    def tearDown(self):self.tmp.cleanup()

    def portable(self):
        if os.name=='nt':return Path(self.real)
        p=self.base/'Downloads'/'TESSERACT'/'tesseract.exe'
        p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.real,p);return p

    def test_autodetecta_downloads_sem_path_nem_nome_de_usuario_fixo(self):
        exe=self.base/'Downloads'/'TESSERACT'/'tesseract.exe';exe.parent.mkdir(parents=True);exe.touch()
        with patch.dict(os.environ,{'USERPROFILE':str(self.base),'SHIFT_TESSERACT':''}), \
             patch('ocr_runtime.shutil.which',return_value=None),patch('ocr_runtime.registry_candidates',return_value=[]):
            self.assertEqual(tesseract_exe(self.config),str(exe))

    def test_caminhos_comuns_e_registro(self):
        cases=[('ProgramFiles','Tesseract-OCR'),('ProgramFiles(x86)','Tesseract-OCR'),
               ('LOCALAPPDATA','Programs/Tesseract-OCR'),('LOCALAPPDATA','Tesseract-OCR')]
        for index,(key,subdir) in enumerate(cases):
            with self.subTest(key=key,path=subdir):
                base=self.base/str(index);exe=base/subdir/'tesseract.exe'
                exe.parent.mkdir(parents=True);exe.touch()
                with patch.dict(os.environ,{key:str(base),'SHIFT_TESSERACT':''}), \
                     patch('ocr_runtime.shutil.which',return_value=None),patch('ocr_runtime.registry_candidates',return_value=[]):
                    self.assertEqual(tesseract_exe(self.config),str(exe))
        registered=self.base/'registro.exe';registered.touch()
        with patch.dict(os.environ,{'SHIFT_TESSERACT':''}),patch('ocr_runtime.shutil.which',return_value=None), \
             patch('ocr_runtime.registry_candidates',return_value=[registered]):
            self.assertEqual(tesseract_exe(self.config),str(registered))

    def test_configuracao_salva_reabre_em_outro_processo(self):
        exe=self.portable();save_settings(exe,self.config)
        env=os.environ.copy();env['SHIFT_OCR_CONFIG']=str(self.config);env['SHIFT_TESSERACT']='arquivo-invalido.exe'
        result=subprocess.run([sys.executable,'-c',
            'from ocr_runtime import tesseract_exe; print(tesseract_exe())'],cwd=ROOT,env=env,capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),str(exe))
        self.assertEqual(load_settings(self.config)['tesseract_path'],str(exe))

    def test_caminho_invalido_nao_sobrescreve_configuracao(self):
        exe=self.portable();save_settings(exe,self.config);original=self.config.read_bytes()
        with self.assertRaises(ValueError):save_settings(self.base/'ausente.exe',self.config)
        self.assertEqual(self.config.read_bytes(),original)

    def test_configuracao_corrompida_tem_erro_visivel_sem_conteudo(self):
        self.config.write_text('DADO IDENTIFICAVEL NAO JSON',encoding='utf-8')
        health=check_ocr_health(settings_path=self.config)
        self.assertFalse(health['ok']);self.assertIn('configuração OCR',health['message'])
        self.assertNotIn('IDENTIFICAVEL',json.dumps(health))
        exe=self.portable();save_settings(exe,self.config)
        self.assertTrue(check_ocr_health(settings_path=self.config)['ok'])

    def test_appdata_independe_da_pasta_da_versao(self):
        with patch.dict(os.environ,{'APPDATA':str(self.base),'SHIFT_OCR_CONFIG':''}):
            self.assertEqual(settings_file(),self.base/'CadastroAssistidoShift'/'ocr.json')

    def test_executavel_movido_faz_fallback_para_instalacao_disponivel(self):
        exe=self.base/'removido.exe';exe.touch();save_settings(exe,self.config);exe.unlink()
        self.assertEqual(tesseract_exe(self.config),self.real)

    def test_idioma_ingles_ausente_nao_fica_verde(self):
        models=self.base/'tessdata';models.mkdir()
        shutil.copy2(ROOT/'tessdata/por.traineddata',models/'por.traineddata')
        with patch.dict(os.environ,{'SHIFT_TESSDATA':str(models)}):
            result=check_ocr_health(exe=self.real)
        self.assertFalse(result['ok']);self.assertIn('eng',result['message'])
        self.assertIn('tessdata',result['message'])

    def test_arquivo_que_nao_e_executavel_nao_fica_verde(self):
        wrong=self.base/'errado.exe';wrong.write_text('nao sou um executavel')
        result=check_ocr_health(exe=str(wrong))
        self.assertFalse(result['ok']);self.assertNotIn(str(wrong),result['message'])

    def test_mecanismo_precisa_ler_imagem_para_ficar_verde(self):
        good_config={'exe':self.real,'args':[],'languages':['por','eng'],'requested':'por+eng'}
        outputs=[subprocess.CompletedProcess([],0,'tesseract 5.5',''),
                 subprocess.CompletedProcess([],0,'','')]
        with patch('ocr_runtime.ocr_configuration',return_value=good_config),patch('ocr_runtime.run_local',side_effect=outputs):
            health=check_ocr_health(exe=self.real)
        self.assertFalse(health['ok']);self.assertIn('imagem fictícia',health['message'])

    def test_saude_real_sem_rede_nos_tres_modos(self):
        with patch('socket.socket',side_effect=AssertionError('Rede proibida')):
            health=check_ocr_health(exe=self.real)
        self.assertTrue(health['ok']);self.assertTrue({'por','eng'}.issubset(health['languages']))

    def test_executavel_escolhido_le_imagem_e_pdf_escaneado(self):
        exe=self.portable();save_settings(exe,self.config)
        image=scan_image('GUIA DE AUTORIZACAO\n'+TEXT)
        path=self.base/'guia fictícia.png';image.save(path)
        pdf=self.base/'guia fictícia.pdf';stream=io.BytesIO();image.save(stream,format='PNG')
        d=pymupdf.open();p=d.new_page(width=760,height=600);p.insert_image(p.rect,stream=stream.getvalue());d.save(pdf);d.close()
        for file in [path,pdf]:
            with self.subTest(format=file.suffix),patch('socket.socket',side_effect=AssertionError('Rede proibida')):
                doc=read_document(file,settings_path=self.config)
                model=parse_document(doc,catalog_load(ROOT/'catalogo_demo.json'))
                self.assertIn('OCR',doc['pages'][0]['method']);self.assertFalse(doc['pages'][0]['warnings'])
                self.assertEqual(model['fields']['Paciente']['value'],'PESSOA SINTETICA ALFA')
                self.assertEqual(model['fields']['Guia']['value'],'TESTE-001')
                self.assertEqual(len(model['exams']),2)

    def test_argumentos_windows_sem_janela_sem_shell(self):
        with patch('ocr_runtime.os.name','nt'),patch('ocr_runtime.subprocess.run') as run:
            run_local(['tesseract.exe','caminho com espaços.png','stdout'])
        self.assertEqual(run.call_args.kwargs['creationflags'],0x08000000)
        self.assertNotIn('shell',run.call_args.kwargs)
        self.assertEqual(run.call_args.args[0][1],'caminho com espaços.png')

    def test_auxiliar_instalador_sem_python_embutido(self):
        script=ROOT/'instalacao_aux.py'
        for action in ['python','localizar-ocr']:
            result=subprocess.run([sys.executable,str(script),action],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(Path(result.stdout.strip()).is_file())
        bad=subprocess.run([sys.executable,str(script),'invalido'],capture_output=True,text=True)
        self.assertEqual(bad.returncode,2);self.assertNotIn('SyntaxError',bad.stderr)
        import instalacao_aux
        with patch('ocr_runtime.tesseract_exe',return_value=None):
            self.assertEqual(instalacao_aux.main(['localizar-ocr']),3)
