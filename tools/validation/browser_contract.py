"""Lightweight browser accessibility assertions; no capture or publication."""
A11Y_SCRIPT = """() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e),closed=e.closest('details:not([open])');return !e.closest('[hidden],[inert]')&&(!closed||closed.querySelector(':scope > summary')?.contains(e))&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
 const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map(e=>({level:Number(e.tagName[1]),text:(e.innerText||'').trim()}));
 const unnamedButtons=[...document.querySelectorAll('button')].filter(e=>visible(e)&&!(e.innerText||e.getAttribute('aria-label')||e.title).trim()).length;
 const unnamedLinks=[...document.querySelectorAll('a')].filter(e=>visible(e)&&!(e.innerText||e.getAttribute('aria-label')||e.title).trim()).length;
 const imagesWithoutAlt=[...document.images].filter(e=>visible(e)&&!e.hasAttribute('alt')).length;
 const inputsWithoutLabels=[...document.querySelectorAll('input,select,textarea')].filter(e=>visible(e)&&!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).length;
 const ids=[...document.querySelectorAll('[id]')].map(e=>e.id), duplicates=[...new Set(ids.filter((id,i)=>ids.indexOf(id)!==i))];
 const violations=[];
 if(unnamedButtons)violations.push({severity:'critical',rule:'button-name',count:unnamedButtons});
 if(unnamedLinks)violations.push({severity:'serious',rule:'link-name',count:unnamedLinks});
 if(imagesWithoutAlt)violations.push({severity:'serious',rule:'image-alt',count:imagesWithoutAlt});
 if(inputsWithoutLabels)violations.push({severity:'serious',rule:'label',count:inputsWithoutLabels});
 if(duplicates.length)violations.push({severity:'moderate',rule:'duplicate-id',count:duplicates.length});
 for(let i=1;i<headings.length;i++)if(headings[i].level>headings[i-1].level+1)violations.push({severity:'moderate',rule:'heading-order',count:1});
 return {page_title:document.title,language:document.documentElement.lang||null,landmarks:[...document.querySelectorAll('header,nav,main,aside,footer,[role]')].filter(visible).map(e=>e.getAttribute('role')||e.tagName.toLowerCase()),headings,buttons_without_names:unnamedButtons,links_without_names:unnamedLinks,images_without_alt:imagesWithoutAlt,inputs_without_labels:inputsWithoutLabels,duplicate_ids:duplicates,violations};
}"""
