"""Guias dos 11 campos essenciais e lotes inteiramente fictícios."""
from pathlib import Path
import hashlib,json,pymupdf
from gerar_exemplos_tiss import make_guide,VALUES,NAMES,CODES
from gerar_exemplos_2_4 import combine,raster

PATIENTS=['PESSOA FICTICIA DE OLIVEIRA','PESSOA FICTICIA DOS SANTOS']
CARDS=['0000087654','0000099999']
CLINICAL='INVESTIGACAO FICTICIA DE ANEMIA.\nHEMOGRAMA PARA AVALIACAO; NAO E NOVO PEDIDO.'
EXECUTOR='LABORATORIO FICTICIO DOS SANTOS'
PRIORITY=[2,3,7,5,10,8,15,17,18,23,30]

def order(path,person=0):
 d=pymupdf.open();p=d.new_page(width=1100,height=1100)
 lines=['PEDIDO MEDICO - FICTICIO','Paciente: '+PATIENTS[person],'Nascimento: '+('01/02/1995' if person==0 else '03/04/1990'),'Carteira: '+CARDS[person],'Medico: DRA EXEMPLO SINTETICA','Conselho: CRM','Numero conselho: 0012345','UF conselho: GO','Exames:']
 lines.extend(f'{name} | 1 | {code}' for name,code in zip(NAMES,CODES));p.insert_text((35,50),'\n'.join(lines),fontsize=14);d.save(path,deflate=True);d.close()

def guide(path,person=0,blank=False,uncertain=False,missing=False,no_procedures=False):
 base=path.with_name(path.stem+'_base.pdf');make_guide(base,other=person==1)
 with pymupdf.open(base) as d:
  p=d[0]
  for rect in [(742,225,1090,250),(30,345,380,380)]:p.add_redact_annot(pymupdf.Rect(rect))
  if person==1:p.add_redact_annot(pymupdf.Rect(30,35,1090,60))
  if blank:
   for rect in [(388,110,740,145),(30,168,380,203),(742,168,1090,203)]:p.add_redact_annot(pymupdf.Rect(rect))
  if no_procedures:p.add_redact_annot(pymupdf.Rect(25,443,1090,665))
  p.apply_redactions()
  p.insert_text((745,244),PATIENTS[person],fontsize=11)
  if person==1:p.insert_text((35,50),'Nascimento: 03/04/1990   Fonte pagadora: IPASGO   Regime atendimento: AMBULATORIAL',fontsize=12)
  p.insert_text((35,360),'01?2345' if uncertain else '0 0 1 2 3 4 5',fontsize=14)
  p.insert_text((35,395),'23 - Indicacao clinica',fontsize=10)
  p.insert_text((35,418),CLINICAL,fontsize=11)
  p.insert_text((745,395),'19 - Codigo CBO',fontsize=10);p.insert_text((745,418),'225125',fontsize=12)
  p.insert_text((35,720),'29 - Codigo do contratado',fontsize=10);p.insert_text((35,745),'000002929',fontsize=13)
  if not missing:
   p.insert_text((230,720),'30 - Nome do contratado executante',fontsize=10)
   if not blank:p.insert_text((230,745),EXECUTOR,fontsize=14)
  p.insert_text((900,720),'31 - Codigo CNES',fontsize=10);p.insert_text((900,745),'0000031',fontsize=13)
  d.save(path,deflate=True)
 base.unlink()
 return {**VALUES,10:PATIENTS[person],8:CARDS[person],19:'225125',23:CLINICAL,30:'' if blank or missing else EXECUTOR,
         **({3:'',5:'',7:''} if blank else {}),**({17:''} if uncertain else {})}

def main(out=None):
 out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_250';out.mkdir(parents=True,exist_ok=True)
 order(out/'pedido_a.pdf');order(out/'pedido_b.pdf',1)
 expected=guide(out/'guia_completa.pdf');guide(out/'guia_b.pdf',1);guide(out/'guia_campos_vazios.pdf',blank=True);guide(out/'guia_crm_incerto.pdf',uncertain=True);guide(out/'guia_sem_campo30.pdf',missing=True);guide(out/'guia_sem_procedimentos.pdf',no_procedures=True)
 combine(out/'01_um_paciente.pdf',[out/'pedido_a.pdf',out/'guia_completa.pdf'])
 combine(out/'02_dois_pacientes_quatro_paginas.pdf',[out/'pedido_a.pdf',out/'guia_b.pdf',out/'guia_completa.pdf',out/'pedido_b.pdf'])
 combine(out/'03_campos_vazios.pdf',[out/'pedido_a.pdf',out/'guia_campos_vazios.pdf'])
 combine(out/'05_leitura_incerta.pdf',[out/'pedido_a.pdf',out/'guia_crm_incerto.pdf'])
 raster(out/'guia_completa.pdf',out/'04_guia_girada.pdf',90)
 (out/'GABARITO.json').write_text(json.dumps({'somente_ficticios':True,'prioritarios':{str(k):expected[k] for k in PRIORITY},'conselho':'CRM','pacientes':PATIENTS,'carteiras':CARDS,'campo23_nao_e_exame':CLINICAL},ensure_ascii=False,indent=2)+'\n')
 (out/'LEIA-ME.txt').write_text('DOCUMENTOS INTEIRAMENTE FICTICIOS. 01: pedido e guia de uma pessoa. 02: quatro paginas de DUAS pessoas; espera-se dois atendimentos, nunca quatro nem uma mistura. 03: campos 3, 5, 7, 30 vazios; rascunho permitido, finalizacao depende de regras e autorizacao. 04: guia escaneada girada. 05: numero no conselho incerto para correcao manual. Campo 23 e indicacao clinica, nao exame. Nenhum codigo representa mapeamento real do Shift.\n')
 (out/'manifesto_sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.pdf'))},indent=2)+'\n')
 return out

if __name__=='__main__':main()
