# Quy trinh kiem soat chi tieu tai chinh theo du an

## 1. Nguyen tac quan tri

He thong duoc thiet ke cho cong ty khoang 100 nguoi, nhieu du an chay song song. Moi khoan chi phai gan voi mot du an, mot hang muc ngan sach, mot nguoi chiu trach nhiem va mot bang chung.

Nguyen tac cot loi:

- Khong chi neu khong co ngan sach hoac phe duyet ngoai le.
- Khong tu phe duyet khoan chi cua chinh minh.
- Tach bach nguoi de nghi, nguoi phe duyet, nguoi thanh toan va nguoi doi soat.
- Moi giao dich ngan hang/MoMo phai doi soat voi de nghi chi hoac phieu thu.
- Moi thay doi ngan sach, nguoi phe duyet, tai khoan thanh toan phai co audit log.

## 2. Danh muc quan ly

Danh muc nen tao tu dau:

- Cong ty/phap nhan
- Phong ban
- Du an
- Ma ngan sach
- Hang muc chi phi
- Nha cung cap
- Hop dong/don hang
- Tai khoan ngan hang/vi dien tu
- Nhan su va vai tro
- Han muc phe duyet

## 3. Vong doi ngan sach du an

1. Tao du an
2. Lap ngan sach tong
3. Chia ngan sach theo hang muc
4. Gan nguoi so huu ngan sach
5. Khoa baseline ngan sach
6. Theo doi cam ket chi
7. Ghi nhan chi thuc te
8. Doi soat thanh toan
9. Bao cao sai lech
10. Dong du an

Chi so kiem soat:

- Budget: ngan sach duoc phe duyet
- Committed: da cam ket qua PO/hop dong/de nghi chi da phe duyet
- Actual: da thanh toan hoac da ghi nhan hoa don
- Available: Budget - Committed - Actual
- Burn rate: Actual theo thoi gian
- Variance: Actual so voi Budget

## 4. Quy trinh de nghi chi

Trang thai:

```text
draft -> submitted -> finance_checked -> approved -> scheduled -> paid -> reconciled -> closed
                 \-> rejected
                 \-> need_info
```

Buoc xu ly:

1. Nguoi de nghi tao yeu cau tren Telegram hoac web.
2. He thong bat buoc co du an, hang muc, so tien, ly do, nha cung cap, bang chung.
3. AI local doc noi dung/anh hoa don neu co, goi y hang muc va canh bao trung lap.
4. Finance controller kiem tra ngan sach, chung tu, thue, hop dong.
5. Quan ly du an phe duyet neu trong han muc.
6. CFO/CEO phe duyet neu vuot han muc, vuot ngan sach, chi nha cung cap moi, hoac chi bat thuong.
7. Ke toan len lich thanh toan.
8. Treasury thanh toan qua ngan hang/MoMo.
9. He thong nhan webhook/sao ke va doi soat.
10. Dong yeu cau va ghi audit log.

## 5. Ma tran han muc de xuat

| Gia tri VND | Phe duyet toi thieu |
|---:|---|
| <= 2,000,000 | Project Manager |
| <= 20,000,000 | Project Manager + Finance Controller |
| <= 100,000,000 | Department Head + Finance Manager |
| <= 500,000,000 | CFO |
| > 500,000,000 | CEO/Board |

Dieu kien bat buoc day len cap cao hon:

- Vuot ngan sach hang muc
- Nha cung cap moi chua duoc xac minh
- Thanh toan truoc hop dong
- Giao dich tien mat hoac vi ca nhan
- Tach nho giao dich trong 7 ngay
- Trung noi dung, trung so tien, trung nha cung cap

## 6. Quy trinh tam ung va hoan ung

Tam ung:

```text
request -> approval -> payout -> expense_capture -> settlement -> close
```

Kiem soat:

- Tam ung phai co han hoan ung.
- Mot nhan su khong duoc co qua 2 khoan tam ung dang mo, tru khi CFO cho phep.
- Qua han hoan ung tu dong nhac Telegram va dua vao bao cao rui ro.

## 7. Doi soat

Doi soat gom 3 lop:

- Doi soat giao dich: giao dich ngan hang/MoMo khop voi payment request.
- Doi soat chung tu: hoa don, hop dong, PO, bien ban nghiem thu.
- Doi soat ngan sach: actual va committed khong vuot han muc.

Quy tac matching:

- Ma noi dung chuyen khoan uu tien: `INVMMC-{project_code}-{request_id}`
- So tien khop tuyet doi voi thanh toan noi dia.
- Thoi gian khop trong cua so 3 ngay.
- Nha cung cap/tai khoan nhan phai khop voi master data.

## 8. Bao cao cho ban dieu hanh

Bao cao hang ngay:

- Tong chi trong ngay
- Khoan chi cho phe duyet
- Giao dich chua doi soat
- Du an vuot 80% ngan sach

Bao cao hang tuan:

- Budget vs Actual theo du an
- Top 10 hang muc chi
- Aging tam ung
- Nha cung cap moi
- Canh bao gian lan/chia nho giao dich

Bao cao hang thang:

- P&L theo du an
- Cash out forecast
- Variance analysis
- Rui ro va khuyen nghi hanh dong
