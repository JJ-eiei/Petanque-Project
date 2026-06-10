@echo off
chcp 65001
color 0A
echo ===================================================
echo       🚀 PETANQUE AI TRACKER (FULL SYSTEM) 🚀
echo ===================================================
echo.

echo [1/3] กำลังเริ่มต้น Backend Server (AI ^& API)...
start "Petanque Backend" cmd /k "python app20-production.py"

echo [2/3] กำลังเริ่มต้น Frontend Server (Web UI)...
start "Petanque Frontend" cmd /k "python -m http.server 8080"

echo รอให้ AI โหลดโมเดล 5 วินาที...
timeout /t 5 /nobreak > NUL

echo [3/3] กำลังเปิดหน้าเว็บเบราว์เซอร์...
:: เปลี่ยนชื่อไฟล์ HTML ด้านล่างให้ตรงกับหน้าที่คุณอยากให้เด้งขึ้นมาหน้าแรก
start chrome "http://localhost:8080/pet24-production.html"

echo.
echo ✅ เปิดระบบสำเร็จ! 
echo ⚠️ หากต้องการเลิกใช้งาน ให้ปิดหน้าต่างสีดำทั้ง 2 บานได้เลยครับ
echo ===================================================
pause