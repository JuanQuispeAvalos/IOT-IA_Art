// Copyright (C) 2019  Jeremy Webb

// This file is part of IOTA Canvas.

// IOTA Canvas is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// IOTA Canvas is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with IOTA Canvas.  If not, see <http://www.gnu.org/licenses/>.


class ArtContainer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      art_prefs: [],
    };
  }

  render() {
    return (
      <div>
        <p>Coming Soon!</p>
        <p>Not Implemented</p>
      </div>
    );
  }
}

class IotaContainer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      error: null,
      isLoaded: false,
      current_balance: null,
    };

    this.handleInputChange = this.handleInputChange.bind(this);
  }

  componentDidMount() {
    setTimeout(() => this.getData(), 100);
  }

  handleInputChange(event) {
    const target = event.target;
    const value = target.type === 'checkbox' ? target.checked : target.value;
    const name = target.name;

    this.setState({
      [name]: value
    });
  }

  getData() {
    fetch("/iota_settings")
      .then(res => res.json())
      .then(
        (result) => {
          result.isLoaded = true;
          this.setState(result);
        },
        // Note: it's important to handle errors here
        // instead of a catch() block so that we don't swallow
        // exceptions from actual bugs in components.
        (error) => {
          this.setState({
            isLoaded: true,
            error
          });
        }
      )
    fetch("/iota_balance")
      .then(res => res.json())
      .then(
        (result) => {
          this.setState(result);
        },
        // Note: it's important to handle errors here
        // instead of a catch() block so that we don't swallow
        // exceptions from actual bugs in components.
        (error) => {
          this.setState({
            current_balance: "Error retrieving balance"
          });
        }
      )
  }

  render() {
    const { error, isLoaded, iota_settings } = this.state;
    if (this.state.error) {
      return <div>Error: {this.state.error.message}</div>;
    } else if (!this.state.isLoaded) {
      return <div>Loading...</div>;
    } else {
      let balance = "Loading..."
      if (this.state.current_balance != null) {
        balance = this.state.current_balance;
      }
      return (
        <div className="IOTA">
          <p><span className="label">Current Balance:</span> {balance}</p>
          <div>
            <p id="addr"><span className="label">Receive Address:</span> {this.state.receive_address}
              <button onClick={() => { navigator.clipboard.writeText(this.state.receive_address) }}>
                <svg xmlns="https://www.w3.org/2000/svg" width="24px" height="24px" viewBox="0 0 24 24" fill="#757575">
                  <path d="M0 0h24v24H0z" fill="none"></path>
                  <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"></path>
                </svg>
              </button>
            </p>
          </div>
          <img id="qr" src="/static/images/receive_address_qr.jpg" alt="IOTA receive address qr code" height="256" width="256"></img>
        </div>
      );
    }
  }
}

class SettingsContainer extends React.Component {
  HOURS_PER_DAY = 24;
  HOURS_PER_WEEK = 168;
  HOURS_PER_MONTH = 5040;

  constructor(props) {
    super(props);
    this.state = {
      error: null,
      isLoaded: false,
      user_settings: null,
    };

    this.handleInputChange = this.handleInputChange.bind(this);
  }

  getRefreshUnit(refresh_time) {
    if (refresh_time / HOURS_PER_MONTH > 0) {
      return HOURS_PER_MONTH
    }
  }

  componentDidMount() {
    setTimeout(() => this.getData(), 100);
  }

  handleInputChange(event) {
    const target = event.target;
    const value = target.type === 'checkbox' ? target.checked : target.value;
    const name = target.name;

    this.setState({
      [name]: value
    });

    // send update to server
    fetch('/update_settings', {
      method: 'POST',
      body: JSON.stringify({
        [name]: value
      }),
      headers: new Headers({
        'Content-Type': 'application/json,'
      })
    }).then(res => res.text());
  }

  getData() {
    fetch("/user_settings")
      .then(res => res.json())
      .then(
        (result) => {
          result.isLoaded = true;
          this.setState(result);
        },
        // Note: it's important to handle errors here
        // instead of a catch() block so that we don't swallow
        // exceptions from actual bugs in components.
        (error) => {
          this.setState({
            isLoaded: true,
            error
          });
        }
      )
  }

  render() {
    const { error, isLoaded, user_settings } = this.state;
    if (error) {
      return <div>Error: {error.message}</div>;
    } else if (!isLoaded) {
      return <div>Loading...</div>;
    } else {
      return (
        <form>
          <label>
            Art Refresh Enabled
          <input
              name="art_refresh_enabled"
              className="switch"
              type="checkbox"
              checked={this.state.art_refresh_enabled}
              onChange={this.handleInputChange} />
          </label>
          <p><label className="full-width">
            Art Refresh Rate
            </label>
            <span><input
              name="art_refresh_rate"
              id="refresh_rate_input"
              type="number"
              value={this.state.art_refresh_rate}
              onChange={this.handleInputChange} />
              <select value={this.state.refresh_unit} onChange={this.handleChange}>
                <option value="1">Hours</option>
                <option value="{HOURS_PER_DAY}">Days</option>
                <option value="{HOURS_PER_WEEK}">Weeks</option>
                <option value="{HOURS_PER_MONTH}">Months</option>
              </select>
            </span>
          </p>
          <p>
            <label className="full-width">
              AI Marketplace URL
              </label>
            <input name="ai_marketplace_url"
              type="text"
              value={this.state.ai_marketplace_url}
              onChange={this.handleInputChange} />
          </p>
          <p>
            <label>
              Energy Saver Enabled
            <input name="display_off_enabled"
                className="switch"
                type="checkbox"
                checked={this.state.display_off_enabled}
                onChange={this.handleInputChange} />
            </label>
          </p>
          <fieldset className="gpios">
            <p>
              <label>
                Setup GPIO
            </label>
              <input name="gpio_setup"
                type="number"
                value={this.state.gpio_setup}
                onChange={this.handleInputChange} />
            </p>
            <p>
              <label>
                Skip GPIO
            </label>
              <input name="gpio_skip"
                type="number"
                value={this.state.gpio_skip}
                onChange={this.handleInputChange} />
            </p>
            <p>
              <label>
                Like GPIO
            </label>
              <input name="gpio_like"
                type="number"
                value={this.state.gpio_like}
                onChange={this.handleInputChange} />
            </p>
          </fieldset>
        </form>
      );
    }
  }
}

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      page: App.PAGES.IOTA,
    };
    this.handleNav = this.handleNav.bind(this);
  }

  static get PAGES() {
    return Object.freeze({ "IOTA": 0, "SETTINGS": 1, "ARTPREFS": 2 });
  }

  handleNav(event) {
    this.setState({ page: App.PAGES[event.target.dataset.page] });
    event.preventDefault();
  }

  render() {
    let appPanel = null;
    let iotaclass = "";
    let generalclass = "";
    let artclass = "";
    switch (this.state.page) {
      case App.PAGES.IOTA:
        appPanel = <IotaContainer />;
        iotaclass = "selected";
        break;
      case App.PAGES.SETTINGS:
        appPanel = <SettingsContainer />;
        generalclass = "selected";
        break;
      case App.PAGES.ARTPREFS:
        appPanel = <ArtContainer />;
        artclass = "selected";
        break;
    }
    return (
      <div>
        <nav className="tab">
          <a href="/iota_settings" data-page="IOTA" className={iotaclass} onClick={this.handleNav}>IOTA</a>
          <a href="/" data-page="SETTINGS" className={generalclass} onClick={this.handleNav}>GENERAL</a>
          <a href="/art_preferences" data-page="ARTPREFS" className={artclass} onClick={this.handleNav}>ART</a>
        </nav>
        {appPanel}
      </div>
    );
  }
}

ReactDOM.render(
  <App />,
  document.getElementById('settings_layout')
);

function debounce(fn, delay) {
  var timer = null;
  return function () {
    var context = this, args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () {
      fn.apply(context, args);
    }, delay);
  };
}