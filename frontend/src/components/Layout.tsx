import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <>
      <header className="site-header">
        <div className="wrap">
          <h1>How Slow Is Justice?</h1>
          <p>Predicted time to a decision in Maharashtra's district courts</p>
          <nav>
            <NavLink to="/" end>Predict</NavLink>
            <NavLink to="/insights">Insights</NavLink>
          </nav>
        </div>
      </header>
      <main className="wrap">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="wrap">
          Statistical estimate from Maharashtra district court records, 2010–2018 (Development Data Lab,
          CC BY-NC-SA 4.0). It describes how long similar cases took, not the outcome of any case, and
          compares court establishments, not judges. Not legal advice.
        </div>
      </footer>
    </>
  );
}
