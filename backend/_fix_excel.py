import os, re, unicodedata, openpyxl, shutil
os.environ.setdefault('DJANGO_SETTINGS_MODULE','cotidjango.settings')
import django
django.setup()
from products.models import Category

path=r'C:\Users\facun\OneDrive\Escritorio\CotiWeb\Exportacion-productos-03-02-26.xlsx'
backup=path.replace('.xlsx','._backup.xlsx')
fixed=path.replace('.xlsx','.fixed.xlsx')

cats=list(Category.objects.all())
by_id={c.id:c for c in cats}

full_paths={}

def norm(s):
    return re.sub(r'\s+',' ', ''.join(ch for ch in unicodedata.normalize('NFD', str(s)) if unicodedata.category(ch)!='Mn')).strip().lower()

for c in cats:
    parts=[]
    cur=c
    seen=set()
    while cur and cur.id not in seen:
        seen.add(cur.id)
        parts.append(cur.nombre)
        cur=by_id.get(cur.parent_id)
    full_paths[c.id]=list(reversed(parts))

path_map={}
leaf_map={}
for parts in full_paths.values():
    path=' > '.join(parts)
    path_map[norm(path)]=path
    leaf=parts[-1]
    leaf_map.setdefault(norm(leaf), set()).add(path)

wb=openpyxl.load_workbook(path)
ws=wb.active
headers=[c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
if 'Categor?as' not in headers:
    raise SystemExit('No Categor?as column found')
col_idx=headers.index('Categor?as')

changed=0
unmatched=[]
for row in ws.iter_rows(min_row=2):
    cell=row[col_idx]
    val=cell.value
    if not val:
        continue
    sval=str(val).strip()
    nval=norm(sval)
    nval=' > '.join([p.strip() for p in nval.split('>')])
    new=None
    if nval in path_map:
        new=path_map[nval]
    else:
        leaf=norm(sval.split('>')[-1].strip())
        candidates=leaf_map.get(leaf)
        if candidates:
            new=sorted(candidates, key=lambda x: x.count('>'))[0]
    if new and new!=sval:
        cell.value=new
        changed+=1
    elif not new:
        unmatched.append(sval)

wb.save(fixed)
shutil.copy2(path, backup)
print('fixed_saved', fixed)
print('backup_saved', backup)
print('changed', changed)
print('unmatched', len(unmatched))
print('sample_unmatched', unmatched[:15])
