import {
  GraduationCap,
  LayoutGrid,
  SlidersHorizontal,
  ClipboardCheck,
  Settings2,
  ChevronRight,
} from 'lucide-react';
import type { Page } from '../hooks/usePageNavigation';

export function SideNavigation({
  page,
  preferencesOpen,
  ready,
  dirty,
  onNavigate,
  onPreferences,
}: {
  page: Page;
  preferencesOpen: boolean;
  ready: boolean;
  dirty: boolean;
  onNavigate: (page: Page) => void;
  onPreferences: () => void;
}) {
  return (
    <aside className="side-navigation" aria-label="功能导航">
      <button className="side-brand" aria-label="有序选课首页" onClick={() => onNavigate('selection')}>
        <span className="nav-icon">
          <GraduationCap size={26} strokeWidth={1.7} />
        </span>
        <span className="nav-copy">
          <strong>
            有序<span>选课</span>
          </strong>
          <small>让课程安排更从容</small>
        </span>
      </button>
      <nav className="side-links" aria-label="选课功能">
        <button
          className={`side-link ${page === 'selection' && !preferencesOpen ? 'active' : ''}`}
          aria-label="选课工作台"
          aria-current={page === 'selection' && !preferencesOpen ? 'page' : undefined}
          onClick={() => onNavigate('selection')}
        >
          <span className="nav-icon">
            <LayoutGrid size={20} />
          </span>
          <span className="nav-copy">
            <strong>选课工作台</strong>
            <small>查看课表与推荐方案</small>
          </span>
        </button>
        <button
          className={`side-link ${preferencesOpen ? 'active' : ''}`}
          aria-label="偏好设置"
          aria-haspopup="dialog"
          aria-expanded={preferencesOpen}
          disabled={!ready}
          onClick={onPreferences}
        >
          <span className="nav-icon">
            <SlidersHorizontal size={20} />
            {dirty && <i className="nav-dirty-dot" />}
          </span>
          <span className="nav-copy">
            <strong>偏好设置</strong>
            <small>{dirty ? '有尚未保存的偏好' : '课程喜好与早课安排'}</small>
          </span>
        </button>
        <button
          className={`side-link ${page === 'results' && !preferencesOpen ? 'active' : ''}`}
          aria-label="录取结果"
          aria-current={page === 'results' && !preferencesOpen ? 'page' : undefined}
          onClick={() => onNavigate('results')}
        >
          <span className="nav-icon">
            <ClipboardCheck size={20} />
          </span>
          <span className="nav-copy">
            <strong>录取结果</strong>
            <small>已获课程与需求完成度</small>
          </span>
        </button>
      </nav>
      <div className="side-bottom">
        <button
          className={`side-link ${page === 'demo' && !preferencesOpen ? 'active' : ''}`}
          aria-label="演示控制"
          aria-current={page === 'demo' && !preferencesOpen ? 'page' : undefined}
          onClick={() => onNavigate('demo')}
        >
          <span className="nav-icon">
            <Settings2 size={20} />
          </span>
          <span className="nav-copy">
            <strong>演示控制</strong>
            <small>推进阶段与重置样例</small>
          </span>
        </button>
        <div className="side-hint">
          <span className="nav-icon">
            <ChevronRight size={15} />
          </span>
          <span className="nav-copy">移出侧栏即可收起</span>
        </div>
      </div>
    </aside>
  );
}
