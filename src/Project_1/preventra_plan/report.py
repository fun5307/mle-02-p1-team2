"""Plan-derived report and canonical SIF candidates, independent of chat history.

Timeline geometry/overlap emphasis adapted from teammate field_dashboard._timeline.
The report sections follow briefing_report.safety_briefing_html; no local parquet,
weather guesses, or alternate chatbot routing are imported.
"""
from collections import Counter
from html import escape
import re
import streamlit as st
from preventra_plan import domain


def timeline_html(items, pairs):
    if not items:
        return ''
    start = min(i.start.hour for i in items) * 60
    end = max(i.end.hour * 60 + i.end.minute for i in items)
    span = max(end - start, 60)
    overlap = {i.work_id for a, b, _ in pairs for i in (a, b)}
    rows = []
    for item in items:
        offset = (item.start.hour * 60 + item.start.minute - start) / span * 100
        width = ((item.end.hour - item.start.hour) * 60 + item.end.minute - item.start.minute) / span * 100
        label = f'{item.activity} · {item.start:%H:%M}–{item.end:%H:%M} · {item.area}'
        color = '#185e59' if item.work_id in overlap else '#85b7aa'
        rows.append(f'<div class="pr-row"><div>{escape(label)}</div><div class="pr-track">'
                    f'<span role="img" aria-label="{escape(label, quote=True)}" style="left:{offset:.3f}%;'
                    f'width:{width:.3f}%;background:{color}"></span></div></div>')
    return ('<style>.pr-timeline{color:#173b39}.pr-row{margin:16px 0;font-size:14px}'
            '.pr-track{position:relative;height:18px;background:#edf3f0;border-radius:4px;margin-top:6px}'
            '.pr-track span{position:absolute;height:100%;border-radius:4px}'
            '.pr-axis{display:flex;justify-content:space-between;font-size:13px}</style>'
            f'<div class="pr-timeline"><div class="pr-axis"><span>{start//60:02}:00</span>'
            f'<span>{end//60:02}:{end%60:02}</span></div>' + ''.join(rows) + '</div>')


def case_counts(evidence):
    # Count only an explicit source field; never classify accidents by guesswork.
    counts, seen = Counter(), set()
    for item in evidence:
        identity = item.source.get('doc_id') or (item.title, item.excerpt)
        if identity in seen:
            continue
        seen.add(identity)
        match = re.search(r'(?:^|\n)\s*(?:사고유형|재해유형|재해형태)\s*[:：]\s*([^\n]+)', item.excerpt)
        counts[match.group(1).strip() if match else '유형 미기재'] += 1
    return dict(counts)


def search_cases(query):
    from preventra_agent.tools import SafetyTools
    from preventra_agent.observability import agent_trace
    from preventra_agent.models import AgentResult
    from uuid import uuid4
    try:
        with agent_trace('작업계획 보고서 · ' + query, str(uuid4()),
                         st.session_state.get('preventra_conversation_id')) as trace:
            tool = next(t for t in SafetyTools().build() if t.name == 'search_sif_cases')
            result = tool.invoke({'type':'tool_call', 'id':str(uuid4()),
                                  'name':tool.name, 'args':{'query':query}}, config=trace.config).artifact
            trace.finish(AgentResult(final_answer=f'보고서 검색 후보 {len(result.evidence)}건',
                                     used_tools=[tool.name], status=result.status))
            return result
    except Exception:
        from preventra_agent.models import ToolResult
        return ToolResult('search_sif_cases', 'error', notice='관련 사고사례를 불러오지 못했습니다.')


def render_report(plan, day, selected=''):
    all_items = domain.daily_rows(plan, day)
    items = [i for i in all_items if not selected or i.work_id == selected]
    if not items:
        return
    pairs = domain.coordination_candidates(plan.items, day)
    if selected:
        pairs = tuple(p for p in pairs if selected in (p[0].work_id, p[1].work_id))
    with st.container(key='plus_daily_report', border=True):
        st.markdown('## 작업 안전 보고서')
        st.caption(f'{plan.site} · {day:%Y년 %m월 %d일} · ' + ('선택 작업' if selected else '하루 전체'))
        metrics = st.columns(3)
        metrics[0].metric('예정 작업', f'{len(items)}개')
        metrics[1].metric('조정 확인 조합', f'{len(pairs)}개' + (' 이상' if len(pairs) == 250 else ''))
        metrics[2].metric('미입력 항목이 있는 작업', f'{sum(bool(domain.missing_work_fields(i)) for i in items)}개')
        st.markdown('### 작업 시간대')
        st.caption('진한 막대는 시간·구역 등을 함께 확인할 조정 후보입니다. 위험도 점수가 아닙니다.')
        st.html(timeline_html(items, pairs))
        totals = Counter()
        for i in items:
            totals[i.area or '구역 미입력'] += ((i.end.hour-i.start.hour)*60+i.end.minute-i.start.minute)/60
        st.markdown('### 구역별 계획 작업시간')
        st.bar_chart([{'구역': area, '작업시간': round(hours, 2)} for area, hours in totals.items()],
                     x='구역', y='작업시간', color='#287b70', height=200)
        st.caption('작업별 예정 시간을 합산했습니다. 동시 작업은 각각 포함하며 인원수는 반영하지 않습니다.')
        st.markdown('### 작업 전 확인 사항')
        for i in items:
            st.markdown('**' + escape(i.activity) + f' · {i.start:%H:%M}–{i.end:%H:%M}**')
            st.text('계획된 안전조치: ' + (i.planned_controls or '미입력'))
            st.text('추가 확인: ' + (i.follow_up or '미입력'))
            missing = domain.missing_work_fields(i)
            if missing:
                st.caption('입력 확인: ' + ', '.join(missing))
            st.caption(f'계획서 출처: {i.sheet} {i.row}행 · {i.work_id}')
        st.markdown('### 동시 작업 조정')
        if pairs:
            st.dataframe([{'작업': f'{a.activity} / {b.activity}',
                           '겹치는 시간': f'{max(a.start,b.start):%H:%M}–{min(a.end,b.end):%H:%M}',
                           '확인 이유': ', '.join(reasons)} for a,b,reasons in pairs],
                         hide_index=True, width='stretch')
            st.caption('계획서의 시간·구역 기반 확인 목록입니다. 현장 위험 판정이나 조치 완료를 의미하지 않습니다.')
        else:
            st.caption('계획서에서 함께 조정할 후보가 확인되지 않았습니다.')
        st.markdown('### 관련 사고사례')
        st.caption('기존 SIF 검색으로 조회한 후보 사례입니다. 그래프는 조회된 후보 건수이며 전체 사고 통계·발생 확률이 아닙니다.')
        cache = st.session_state.setdefault('plus_report_cases', {})
        queries = list(dict.fromkeys(f'{i.activity} {i.equipment} 사고사례'.strip() for i in items))
        if len(queries) > 8:
            st.caption('자동 검색은 앞 8개 작업·장비 조합까지 표시합니다. 위에서 작업을 선택하면 개별 조회할 수 있습니다.')
        retrieved = []
        for query in queries[:8]:
            if query not in cache:
                with st.spinner('작업과 관련된 사고사례를 확인하고 있습니다…'):
                    cache[query] = search_cases(query)
                while len(cache) > 64:
                    cache.pop(next(iter(cache)))
            result = cache[query]
            st.markdown('**' + escape(query.removesuffix(' 사고사례')) + '**')
            if result.status == 'error':
                st.warning('관련 사고사례를 불러오지 못했습니다. 계획서 보고서와 상담은 계속 사용할 수 있습니다.')
                if st.button('사례 다시 조회', key='plus_retry_case_' + query):
                    cache.pop(query, None)
                    st.rerun()
                continue
            if not result.evidence:
                st.caption('해당 조건의 검색 후보가 없습니다. 사고가 없다는 뜻은 아닙니다.')
                retrieved.append({'작업·장비': query.removesuffix(' 사고사례'), '조회 건수': 0})
                continue
            counts = case_counts(result.evidence)
            retrieved.append({'작업·장비': query.removesuffix(' 사고사례'), '조회 건수': sum(counts.values())})
            if set(counts) != {'유형 미기재'}:
                st.bar_chart([{'사고유형': name, '조회 건수': n} for name,n in counts.items()],
                             x='사고유형', y='조회 건수', color='#287b70', height=180)
            else:
                st.caption(f'관련 후보 {sum(counts.values())}건 · 검색 자료에 사고유형 분류값이 없어 유형별 집계는 표시하지 않습니다.')
            with st.expander(f'조회 근거 확인 · {sum(counts.values())}건'):
                for evidence in result.evidence:
                    st.text(evidence.title)
                    st.text(evidence.excerpt)
                    source = evidence.source
                    st.caption(' · '.join(str(source[k]) for k in ('source','doc_id','sheet','row_number') if source.get(k)))
        if retrieved:
            st.markdown('#### 작업별 조회 사례 수')
            st.bar_chart(retrieved, x='작업·장비', y='조회 건수', color='#287b70', height=210)
            st.caption('검색에서 반환한 후보 수입니다. 작업 간 중복 사례가 포함될 수 있고 검색 상한의 영향을 받으므로 위험도 비교에는 사용할 수 없습니다. 조회 실패 작업은 제외됩니다.')
