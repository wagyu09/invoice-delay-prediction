# feature

- **buisness_year**
송장이 생성된 연도
- **posting_date**
해당 송장이 ERP 데이터베이스에 입력된 날짜
전기일: 총계정원장에 기록되어 회계쩍으로 인식된 날짜
- **document_create_date**
송장 문서가 생성된 날짜
- **document_create_date.1**`document_create_date`를 정규화한 날짜 형식
- **due_in_date**
고객이 송장을 결제해야 하는 예정일
- **baseline_create_date**
송장이 생성된 기준 날짜
결제 기한 계산을 시작하는 기준점

---

- document_create_date는 시스템 로그에 가까워서 별로 중요하지 않음
- 다중공선성 제거: [document_create_date, document_create_date.1, posting_date**] 삭제
	(모두 baseline_create_date와 상관계수 1)
- [due_in_date, baseline_create_date] 데이터 타입을 datetime으로 변경
- 계절성/패턴 추출을 위해 **baseline_create_date** 에서 월, 일, 요일 추출해 새 피쳐 생성 [baseline_month, baseline_day, baseline_dayofweek]
- **Allowed_Pay_Days** = due_in_date - baseline_create_date으로 새 칼럼 생성. 고객에게 주어진 총 결제 유예 기간
- dataset에는 넣지 않았으나 delay feature 생성해 Allowed_Pay_Days와 correlation matrix 그려봤을 때 -0.231
	- 고객에게 부여된 결제 유예 기간이 길수록 지연 일수가 줄어드는 경향 확인됨
- 추가 분석: 실제 결제일과 예정일의 차이를 계산한 결과, 특정 결제 조건(예: CAX2, NAX2 등)에서 지연이 두드러지게 발생하는 패턴을 확인
	
- <class 'pandas.core.frame.DataFrame'>
RangeIndex: 50000 entries, 0 to 49999
Data columns (total 20 columns):
 #   Column                Non-Null Count  Dtype         
---  ------                --------------  -----         
 0   business_code         50000 non-null  object        
 1   cust_number           50000 non-null  object        
 2   name_customer         50000 non-null  object        
 3   clear_date            40000 non-null  object        
 4   buisness_year         50000 non-null  float64       
 5   doc_id                50000 non-null  float64       
 6   due_in_date           50000 non-null  datetime64[ns]
 7   invoice_currency      50000 non-null  object        
 8   document type         50000 non-null  object        
 9   posting_id            50000 non-null  float64       
 10  area_business         0 non-null      float64       
 11  total_open_amount     50000 non-null  float64       
 12  baseline_create_date  50000 non-null  datetime64[ns]
 13  cust_payment_terms    50000 non-null  object        
 14  invoice_id            49994 non-null  float64       
 15  isOpen                50000 non-null  int64         
 16  baseline_month        50000 non-null  int32         
 17  baseline_day          50000 non-null  int32         
 18  baseline_dayofweek    50000 non-null  int32         
 19  Allowed_Pay_Days      50000 non-null  int64         
dtypes: datetime64[ns](2), float64(6), int32(3), int64(2), object(7)