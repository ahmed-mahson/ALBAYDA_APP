document.addEventListener('DOMContentLoaded', () => {
    // دالة لجلب أنواع القضايا والقضاة
    async function loadOptions() {
        try {
            const response = await fetch('/api/cases/options', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_type: 'all' })
            });
            const data = await response.json();
            
            // تعبئة قائمة أنواع القضايا
            const typeSelects = document.querySelectorAll('select[data-types]');
            typeSelects.forEach(select => {
                select.innerHTML = '<option value="all">كل الأنواع</option>';
                data.case_types.forEach(type => {
                    select.innerHTML += `<option value="${type}">${type}</option>`;
                });
            });

            // تعبئة قائمة القضاة
            const judgeSelects = document.querySelectorAll('select[data-judges]');
            judgeSelects.forEach(select => {
                select.innerHTML = '<option value="all">كل القضاة</option>';
                data.judges.forEach(judge => {
                    select.innerHTML += `<option value="${judge}">${judge}</option>`;
                });
            });
        } catch (error) {
            console.error('Failed to load options:', error);
        }
    }

    // استدعاء الدالة عند فتح الصفحة
    loadOptions();
});
