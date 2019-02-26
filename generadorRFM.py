
"""API Generador-RFM"""

import pymysql
import json
import time
import pandas as pd
import numpy as np

from flask import Flask,Response,request
from sklearn.cluster import KMeans





app = Flask(__name__)

host=None
db=None
user_db=None
pass_db=None
query_fix="SET sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));"

id_RFM=None
nombre_RFM=None
target_R=None
target_F=None
target_M=None






@app.route("/setRFM",methods=['POST'])
def setRFM(body=None):

	"""API que genera RFM para todas las cuentas"""
	body=request.get_json()
	if body==None:
		msj= "No se enviaron parametros POST, por lo tanto el proceso se detuvo"
		return Response(status=400,response=msj)
	else:
		check=checkBodysetRFM(body)
		if (check!='OK'):
			return check


	segmentos=body['segmentos']
	ponderaciones=body['ponderaciones']
	info_db=body['db']		

	global host
	global db
	global user_db
	global pass_db

	host=info_db[0]['host']
	db=info_db[1]['db']
	user_db=info_db[2]['user']
	pass_db=info_db[3]['password']


	try:
		conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)

		cur=conn.cursor()

		#----Modify-----
		query_extract="SELECT Id_cliente,Nombre,max(Fecha) as 'Recencia',count(Monto) as 'Frecuencia',AVG(Monto) as 'Monto' FROM rfm_in group by Id_cliente;"
		#----Modify-----
		
		cur.execute(query_fix)
		cur.execute(query_extract)

		res = cur.fetchall()

		cur.close()

		conn.close()

	except pymysql.Error as e:
		msj= ("Error %d: %s" % (e.args[0], e.args[1]))
		print(msj)
		return Response(status=400,response=msj)

	else:
		global id_RFM
		global nombre_RFM
		global target_R
		global target_F
		global target_M

		#----Modify-----
		headers=['id','Nombre','Recencia','Frecuencia','Monto']

		id_RFM=headers[0]
		nombre_RFM=headers[1]
		target_R=headers[2]
		target_F=headers[3]
		target_M=headers[4]
		#----Modify-----		
		dataset_dummy={}
		filas=0

		for h in headers:
			dataset_dummy[h]=[]
			
		if(len(res)>0):
			for r in res:
				filas+=1
				for i in range(len(headers)):
					dataset_dummy[headers[i]].append(r[i])
		else:
			msj= "No hay registros para iniciar el proceso."
			return Response(status=400,response=msj)

		print('El numero de filas de este dataset es de:'+str(filas))

		first_dataset=pd.DataFrame(dataset_dummy)


		first_dataset[target_R]=first_dataset[target_R].astype(str).str.replace('\D', '')
		first_dataset[target_R]=first_dataset[target_R].astype(str).astype(int)
		first_dataset[target_R]=first_dataset[target_R].fillna(first_dataset[target_R].mean())
		first_dataset[target_F]=first_dataset[target_F].fillna(0)
		first_dataset[target_M]=first_dataset[target_M].fillna(0)


		#Llamada a los 3 servicios
		dataset_R=setRecencia(first_dataset)
		dataset_F=setFrecuencia(first_dataset)
		dataset_M=setMonto(first_dataset)


		last_dataset=dataset_R.merge(dataset_F,on=headers).merge(dataset_M,on=headers)
		final_dataset=setCatego(last_dataset,segmentos,ponderaciones)



		msj= 'Operacion concluida, numero de registros afectados:'+str(filas)
		return Response(status=200,response=msj)
		#return last_dataset

@app.route("/setCLV",methods=['POST'])
def setCLV(body=None):
	body=request.get_json()
	if body==None:
		msj= "No se enviaron parametros POST, por lo tanto el proceso se detuvo"
		return Response(status=400,response=msj)
	else:
		check=checkBodysetCLV(body)
		if (check!='OK'):
			return check

	info_db=body['db']		

	global host
	global db
	global user_db
	global pass_db

	host=info_db[0]['host']
	db=info_db[1]['db']
	user_db=info_db[2]['user']
	pass_db=info_db[3]['password']

	if 'meanlife' in body:
		meanlife=body['meanlife']
	else:
		meanlife=getmeanlife()	

	print('Promedio de  vida:',meanlife)

	try:
		conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)

		cur=conn.cursor()

		#----Modify-----
		query_extract="SELECT Id_cliente,Nombre,count(Monto) as 'Frecuencia',AVG(Monto) as 'Monto' FROM rfm_in group by Id_cliente;"
		#----Modify-----
		
		cur.execute(query_fix)
		cur.execute(query_extract)

		res = cur.fetchall()

		cur.close()

		conn.close()

	except pymysql.Error as e:
		msj= ("Error %d: %s" % (e.args[0], e.args[1]))
		print(msj)
		return Response(status=400,response=msj)
	else:
		#----Modify-----
		headers=['id','Nombre','Frecuencia','Monto']
		#----Modify-----		

		dataset_dummy={}
		filas=0

		for h in headers:
			dataset_dummy[h]=[]
			
		if(len(res)>0):
			for r in res:
				filas+=1
				for i in range(len(headers)):
					dataset_dummy[headers[i]].append(r[i])
		else:
			msj= "No hay registros para iniciar el proceso."
			return Response(status=400,response=msj)

		print('El numero de filas de este dataset es de:'+str(filas))

		first_dataset=pd.DataFrame(dataset_dummy)
		first_dataset[headers[2]]=first_dataset[headers[2]].astype(float)
		first_dataset[headers[2]]=first_dataset[headers[2]].fillna(0)
		first_dataset[headers[3]]=first_dataset[headers[3]].fillna(0)

		first_dataset['Client_value']=first_dataset['Frecuencia']*first_dataset['Monto']
		first_dataset['CLV']=first_dataset['Client_value']*float(meanlife)


		conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)
		cur=conn.cursor()

		cont=0
		val=[]
		for index,row in first_dataset.iterrows():
			#query="Update "+table+" set R="+str(int(row['R']))+",F="+str(int(row['F']))+",M="+str(int(row['M']))+",Categoria='"+str(row['Categoria'])+"' where "+id_RFM+"='"+str(row[id_RFM])+"';"
			val.append((row[headers[0]],row[headers[1]],row[headers[2]],row[headers[3]],row['Client_value'],meanlife,row['CLV']))
			cont=cont+1

		print('inserts:',cont)
		try:
			query="insert into clv_out (Id_cliente,Nombre,Frecuencia_in,Monto_in,Valor_cliente,Vida_cliente,CLV) values (%s,%s,%s,%s,%s,%s,%s)"
			cur.executemany(query,val)
			conn.commit()
			cur.close()
			conn.close()
		except pymysql.Error as e:
			msj= ("Error %d: %s" % (e.args[0], e.args[1]))
			print(msj)
			return Response(status=400,response=msj)			
		else:
			msj='Operacion concluida, se insertaron '+str(cont)+' regitros'
			return Response(msj,status=200)
		



def checkBodysetCLV(body):
		c=0
		for i in body:
			if(i!='id' and i!='db' and i!='meanlife'):
				msj= "Key:"+i+" incorrecta,las keys deben ser las siguientes:\"db\",\"meanlife\" (opcional)"
				return Response(status=400,response=msj)
			else:
				c=c+1
		if(c!=3 and c!=1):
				msj= "Falta alguna key,las keys deben ser las siguientes:\"db\",opcional(\"meanlife\")"
				return Response(status=400,response=msj)		

		if 'meanlife' in body:
			if(type(body['meanlife'])!=int):
				msj= "meanlife no es \"entero\",favor de corregir"
				return Response(status=400,response=msj)	

		c=0
		for i in body['db']:
			for key,val in i.items():
				if(key=='host'):
					if(type(val)!=str):
						msj= "El dato de \"host\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='db'):
					if(type(val)!=str):
						msj= "El dato de \"db\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='user'):
					if(type(val)!=str):
						msj= "El dato de \"user\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='password'):
					if(type(val)!=str):
						msj= "El dato de \"password\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				else:
					msj= "Key:"+key+" incorrecta para \"db\",las keys deben ser las siguientes, en el siguiente orden: \"host\",\"db\",\"user\",\"password\""		
					return Response(status=400,response=msj)	
		if(c!=4):
			msj= "Falta alguna key,las keys deben ser las siguientes:\"segmentos\",\"ponderaciones\",\"db\""
			return Response(status=400,response=msj)
		return 'OK'											

def checkBodysetRFM(body):
		c=0
		for i in body:
			if(i!='segmentos' and i!='ponderaciones' and i!='db'):
				msj= "Key:"+i+" incorrecta,las keys deben ser las siguientes:\"segmentos\",\"ponderaciones\",\"db\""
				return Response(status=400,response=msj)
			else:
				c=c+1
		if(c!=3):
				msj= "Falta alguna key,las keys deben ser las siguientes:\"segmentos\",\"ponderaciones\",\"db\""
				return Response(status=400,response=msj)		

		for i in body['segmentos']:
			for key,val in i.items():
				if(key=='nombre'):
					if(type(val)!=str):
						msj= "Uno de los datos de \"Segmentos\" no es \"string\",favor de corregir"
						return Response(status=400,response=msj)
				else:
					msj= "Key:"+key+" incorrecta en  \"segmentos\",debe ser Key:\"nombre\""
					return Response(status=400,response=msj)

		total=0
		c=0
		for i in body['ponderaciones']:
			for key,val in i.items():
				if(key=='recencia'):
					if(type(val)!=int):
						msj= "El dato de \"recencia\" debe ser \"int\" para que la sumatoria de recencia+frecuencia+monto=100,favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1
						total=total+val	
				elif(key=='frecuencia'):
					if(type(val)!=int):
						msj= "El dato de \"frecuencia\" debe ser \"int\" para que la sumatoria de recencia+frecuencia+monto=100,favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1
						total=total+val	
				elif(key=='monto'):
					if(type(val)!=int):
						msj= "El dato de \"monto\" debe ser \"int\" para que la sumatoria de recencia+frecuencia+monto=100,favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1
						total=total+val	
				else:
					msj= "Key:"+key+" incorrecta para \"ponderaciones\",las keys deben ser las siguientes, en el siguiente orden: \"recencia\",\"frecuencia\",\"monto\""
					return Response(status=400,response=msj)
		if ((total>100) | (total<100)):
			msj= "La suma de las ponderaciones recencia+frecuencia+monto deber ser 100, no "+str(total)+", favor de corregir"
			return Response(status=400,response=msj)
		if(c!=3):
			msj= "Falta alguna key,las keys deben ser las siguientes:\"segmentos\",\"ponderaciones\",\"db\""
			return Response(status=400,response=msj)	

		c=0
		for i in body['db']:
			for key,val in i.items():
				if(key=='host'):
					if(type(val)!=str):
						msj= "El dato de \"host\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='db'):
					if(type(val)!=str):
						msj= "El dato de \"db\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='user'):
					if(type(val)!=str):
						msj= "El dato de \"user\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				elif(key=='password'):
					if(type(val)!=str):
						msj= "El dato de \"password\" debe ser \"str\",favor de corregir"
						return Response(status=400,response=msj)
					else:
						c=c+1	
				else:
					msj= "Key:"+key+" incorrecta para \"db\",las keys deben ser las siguientes, en el siguiente orden: \"host\",\"db\",\"user\",\"password\""		
					return Response(status=400,response=msj)	
		if(c!=4):
			msj= "Falta alguna key,las keys deben ser las siguientes:\"segmentos\",\"ponderaciones\",\"db\""
			return Response(status=400,response=msj)
		return 'OK'						

def setRecencia(first_dataset):
	print('Entro a setRecencia')
	dataset=first_dataset

	dataset=dataset.sort_values(by=target_R,ascending=True)
	dataset = dataset.reset_index(drop=True)
	#dataset[target_R]=dataset[target_R].fillna(dataset[target_R].mean())

	model_r=KMeans(n_clusters=5).fit(dataset[[target_R]])
	clust_r=pd.Series(model_r.labels_)
	dataset['p_r']=clust_r
	print('Se genero cluster de setRecencia')

	lim_clusts=[]
	for i in range(0,5):
		x=dataset[dataset['p_r']==i]
		lim_clusts.append(x[target_R].max())
		
	lim_clusts.sort() 

	lim1=lim_clusts[0]
	lim2=lim_clusts[1]
	lim3=lim_clusts[2]
	lim4=lim_clusts[3]
	lim5=lim_clusts[4]

	dataset.loc[(dataset[target_R] <= lim1), 'R'] = 1
	dataset.loc[(dataset[target_R] <= lim2) & (dataset[target_R] > lim1), 'R'] = 2
	dataset.loc[(dataset[target_R] <= lim3) & (dataset[target_R] > lim2), 'R'] = 3
	dataset.loc[(dataset[target_R] <= lim4) & (dataset[target_R] > lim3), 'R'] = 4
	dataset.loc[(dataset[target_R] <= lim5) & (dataset[target_R] > lim4), 'R'] = 5

	dataset=dataset.drop(['p_r'], axis=1)

	return dataset

def setFrecuencia(first_dataset):
	print('Entro a setFrecuencia')
	dataset=first_dataset

	dataset=dataset.sort_values(by=target_F,ascending=True)
	dataset = dataset.reset_index(drop=True)
	#dataset[target_F]=dataset[target_F].fillna(dataset[target_F].mean())

	model_f=KMeans(n_clusters=5).fit(dataset[[target_F]])
	clust_f=pd.Series(model_f.labels_)
	dataset['p_f']=clust_f
	print('Se genero cluster de setFrecuencia')

	lim_clusts=[]
	for i in range(0,5):
		x=dataset[dataset['p_f']==i]
		lim_clusts.append(x[target_F].max())
	lim_clusts.sort()   

	lim1=lim_clusts[0]
	lim2=lim_clusts[1]
	lim3=lim_clusts[2]
	lim4=lim_clusts[3]
	lim5=lim_clusts[4]

	dataset.loc[(dataset[target_F] <= lim1), 'F'] = 1
	dataset.loc[(dataset[target_F] <= lim2) & (dataset[target_F] > lim1), 'F'] = 2
	dataset.loc[(dataset[target_F] <= lim3) & (dataset[target_F] > lim2), 'F'] = 3
	dataset.loc[(dataset[target_F] <= lim4) & (dataset[target_F] > lim3), 'F'] = 4
	dataset.loc[(dataset[target_F] <= lim5) & (dataset[target_F] > lim4), 'F'] = 5

	dataset=dataset.drop(['p_f'], axis=1)

	return dataset	

def setMonto(first_dataset):
	print('Entro a setMonto')
	dataset=first_dataset

	dataset=dataset.sort_values(by=target_M,ascending=True)
	dataset = dataset.reset_index(drop=True)
	#dataset[target_M]=dataset[target_M].fillna(0)

	model_m=KMeans(n_clusters=5).fit(dataset[[target_M]])
	clust_m=pd.Series(model_m.labels_)
	dataset['p_m']=clust_m
	print('Se genero cluster de setMonto')

	lim_clusts=[]
	for i in range(0,5):
		x=dataset[dataset['p_m']==i]
		lim_clusts.append(x[target_M].max())
	lim_clusts.sort()   

	lim1=lim_clusts[0]
	lim2=lim_clusts[1]
	lim3=lim_clusts[2]
	lim4=lim_clusts[3]
	lim5=lim_clusts[4]

	dataset.loc[(dataset[target_M] <= lim1), 'M'] = 1
	dataset.loc[(dataset[target_M] <= lim2) & (dataset[target_M] > lim1), 'M'] = 2
	dataset.loc[(dataset[target_M] <= lim3) & (dataset[target_M] > lim2), 'M'] = 3
	dataset.loc[(dataset[target_M] <= lim4) & (dataset[target_M] > lim3), 'M'] = 4
	dataset.loc[(dataset[target_M] <= lim5) & (dataset[target_M] > lim4), 'M'] = 5

	dataset=dataset.drop(['p_m'], axis=1)

	return dataset		

def setCatego(last_dataset,segmentosx,ponderacionesx):
	print('Entro a setCatego')
	dataset=last_dataset
	segmentos=segmentosx
	ponderaciones=ponderacionesx

	dataset['ponderacion']=dataset['ponderacion']=((dataset['R']*ponderaciones[0]['recencia'])+(dataset['F']*ponderaciones[1]['frecuencia'])+(dataset['M']*ponderaciones[2]['monto']))/100

	model_RFM=KMeans(n_clusters=len(segmentos)).fit(np.array(dataset[['ponderacion']]))
	clust_RFM=pd.Series(model_RFM.labels_)
	dataset['p_RFM']=clust_RFM
	print('Se genero cluster de setCatego')

	lim_clusts=[]
	for i in range(0,len(segmentos)):
		x=dataset[dataset['p_RFM']==i]
		lim_clusts.append(x['ponderacion'].max())

	lim_clusts.sort()  		

	limits={}
	for index,i in enumerate(lim_clusts):
		key = 'limit'+str(index+1)
		value = i
		limits[key] = value


	for index,j in enumerate(limits):
		if j=='limit1':
			dataset.loc[(dataset['ponderacion'] <= limits[j]), 'Segmento'] = segmentos[index]['nombre']
			temp=limits[j]
		else:
			dataset.loc[(dataset['ponderacion']<=limits[j]) & (dataset['ponderacion']>temp), 'Segmento'] = segmentos[index]['nombre']
			temp=limits[j]

	dataset=dataset.drop(['p_RFM'], axis=1)
	dataset['Monto']=dataset['Monto'].astype(float)
	dataset=dataset.round({'Monto': 4})

	#db='RFM_Generator'
	conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)
	cur=conn.cursor()

	cont=0
	val=[]
	for index,row in dataset.iterrows():
		#query="Update "+table+" set R="+str(int(row['R']))+",F="+str(int(row['F']))+",M="+str(int(row['M']))+",Categoria='"+str(row['Categoria'])+"' where "+id_RFM+"='"+str(row[id_RFM])+"';"
		val.append((row[id_RFM],row[nombre_RFM],row[target_R],row[target_F],row[target_M],row['R'],row['F'],row['M'],row['Segmento']))
		cont=cont+1

	print('inserts:',cont)
	try:
		query="insert into rfm_out (Id_cliente,Nombre,Recencia_in,Frecuencia_in,Monto_in,Recencia_out,Frecuencia_out,Monto_out,Segmento) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
		cur.executemany(query,val)
		conn.commit()
		cur.close()
		conn.close()
	except pymysql.Error as e:
		msj= ("Error %d: %s" % (e.args[0], e.args[1]))
		print(msj)
		return Response(status=400,response=msj)			
	else:
		return dataset

def getmeanlife():
		print('Entro a getmeanlife')
		try:
			conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)

			cur=conn.cursor()

			#----Modify-----
			query_accounts="select distinct Id_cliente from rfm_in;"
			#----Modify-----
		
			cur.execute(query_accounts)

			res = cur.fetchall()

			cur.close()

			conn.close()

		except pymysql.Error as e:
			msj= ("Error %d: %s" % (e.args[0], e.args[1]))
			print(msj)
			return Response(status=400,response=msj)
		else:
			filas=0
			ids=[]
			if(len(res)>0):
				for r in res:
					ids.append(r[0])

			print('Total de cuentas:',len(ids))

			meanlife_count=0

			try:
				conn=pymysql.connect(host=host, user=user_db, passwd=pass_db, db=db)

				cur=conn.cursor()

				cont=0

				for id in ids:
					#----Modify-----
					query_meanlife="SELECT TIMESTAMPDIFF(MONTH,(select MAX(Fecha) FROM rfm_in WHERE Id_cliente='%s') , (select MIN(Fecha) FROM rfm_in WHERE Id_cliente='%s'));" %(id,id)
					#----Modify-----
					cur.execute(query_meanlife)

					res = cur.fetchall()

					#print('Resultado de query:',res[0][0])

					if(res[0][0]==None):
						continue

					cont=cont+1
					meanlife_count=meanlife_count+abs(res[0][0])

				#print('Total de meses',meanlife_count)
				print('Cuentas con al menos 1 mes:',cont)

				cur.close()

				conn.close()

			except pymysql.Error as e:
				msj= ("Error %d: %s" % (e.args[0], e.args[1]))
				print(msj)
				return Response(status=400,response=msj)			

			else:
				final_meanlife=meanlife_count/cont
				#print('Vida promedio en meses:',final_meanlife)
				return final_meanlife






if __name__ == '__main__':
	app.run(debug=True, host='0.0.0.0', port=5000)