<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match="/">
    <html>
      <head>
        <style type="text/css">
          a { text-decoration:none; color:#666; }
          a:hover { text-decoration:underline; color:#f00;}
          .no-hover {text-decoration:none; color:#000;}
          .no-hover:hover {text-decoration:none; color:#000;}
          /* Style the buttons that are used to open and close the accordion panel */
          .accordion {
            background-color: #eee;
            font-size: 12pt;
            color: #444;
            cursor: pointer;
            padding: 12px;
            width: 100%;
            text-align: left;
            border: none;
            outline: none;
            transition: 0.4s;
          }

          /* Add a background color to the button if it is clicked on (add the .active class with JS), and when you move the mouse over it (hover) */
          .active, .accordion:hover {
          background-color: #ccc;
          }

          /* Style the accordion panel. Note: hidden by default */
          .panel {
           padding: 0 12px;
           background-color: white;
           max-height: 0;
           overflow: hidden;
           transition: max-height 0.2s ease-out;
          }
          .accordion:after {
          content: '\02795'; /* Unicode character for "plus" sign (+) */
          font-size: 13px;
          color: #777;
          float: right;
          margin-left: 5px;
          }

          .active:after {
          content: "\2796"; /* Unicode character for "minus" sign (-) */
          }

          .fail {
            background-color: #cdba2d;
          }
          .fail:hover {
          background-color: #9d8d24;
          }
        </style>
        <script type="text/javascript" src="accordion.js"></script>
      </head>
      <body onLoad="setup()">
        <h2><a name="test_revision" class="no-hover">Revisions</a></h2>
        <table border="0">
          <tr bgcolor="#9acd32">
            <th>Date</th>
            <th>Code</th>
            <th>Tests</th>
          </tr>
          <tr>
            <xsl:variable name="code_hash" select="Tests/Revisions/code_full"/>
            <xsl:variable name="tests_hash" select="Tests/Revisions/tests_full"/>
            <td style="padding: 0px 10px 0px 10px">
              <xsl:value-of select="Tests/Date/start"/>
            </td>
            <td style="padding: 0px 10px 0px 10px">
              <a href="https://github.com/OPALX-project/OPALX/commit/{$code_hash}" target="_blank">
                <xsl:value-of select="Tests/Revisions/code"/>
              </a>
            </td>
            <td style="padding: 0px 10px 0px 10px">
              <a href="https://github.com/OPALX-project/regression-tests-x/commit/{$tests_hash}" target="_blank">
                <xsl:value-of select="Tests/Revisions/tests"/>
              </a>
            </td>
          </tr>
        </table>
        <h2>Regression Tests</h2>
        <xsl:if test="count(Tests/Simulation/Test[state]) &gt; 0">
          <table border="0" style="margin-bottom: 25px">
            <tr bgcolor="#9acd32">
              <th style="padding: 2px 16px 2px 16px;">Passed</th>
              <th style="padding: 2px 16px 2px 16px;">Broken</th>
              <th style="padding: 2px 16px 2px 16px;">Failed</th>
              <th style="padding: 2px 16px 2px 16px;">Total</th>
            </tr>
            <tr>
              <td style="text-align: center"><xsl:value-of select="count(Tests/Simulation/Test[state='passed'])"/></td>
              <td style="text-align: center"><xsl:value-of select="count(Tests/Simulation/Test[state='broken'])"/></td>
              <td style="text-align: center"><xsl:value-of select="count(Tests/Simulation/Test[state='failed'])"/></td>
              <td style="text-align: center"><xsl:value-of select="count(Tests/Simulation/Test)"/></td>
            </tr>
          </table>
        </xsl:if>
        <xsl:for-each select="Tests/Simulation">
          <xsl:variable name="simname" select="@name"/>
          <xsl:choose>
            <xsl:when test="count(Test[passed]) &gt; 0">
              <xsl:choose>
                <xsl:when test="count(Test) != count(Test[passed='true'])">
                  <button class="accordion fail">
                    <b style="margin-right:40px"><xsl:value-of select="@name"/></b>
                    [passed: <xsl:value-of select="count(Test[passed='true'])"/> | broken or failed: <xsl:value-of select="count(Test[passed='false'])"/> ]
                  </button>
                </xsl:when>
                <xsl:otherwise>
                  <button class="accordion">
                    <b style="margin-right:40px"><xsl:value-of select="@name"/></b>
                    [passed: <xsl:value-of select="count(Test[passed='true'])"/> | broken or failed: <xsl:value-of select="count(Test[passed='false'])"/> ]
                  </button>
                </xsl:otherwise>
              </xsl:choose>
            </xsl:when>
            <xsl:otherwise>
              <xsl:choose>
                <xsl:when test="count(Test) != count(Test[state='passed'])">
                  <button class="accordion fail"> <b style="margin-right:40px"><xsl:value-of select="@name"/></b>
                  [passed: <xsl:value-of select="count(Test[state='passed'])"/> | broken: <xsl:value-of select="count(Test[state='broken'])"/> | failed: <xsl:value-of select="count(Test[state='failed'])"/> ]
                  </button>
                </xsl:when>
                <xsl:otherwise>
                  <button class="accordion"> <b style="margin-right:40px"><xsl:value-of select="@name"/></b>
                  [passed: <xsl:value-of select="count(Test[state='passed'])"/> | broken: <xsl:value-of select="count(Test[state='broken'])"/> | failed: <xsl:value-of select="count(Test[state='failed'])"/> ]
                  </button>
                </xsl:otherwise>
              </xsl:choose>
            </xsl:otherwise>
          </xsl:choose>
          <div class="panel">
            <p>
              <!--<h3>Simulation: <xsl:value-of select="@name"/></h3>-->
              Description: <xsl:value-of select="@description"/>
              <table border="0">
                <tr bgcolor="#9acd32">
                  <th>Variable</th>
                  <th>Mode</th>
                  <th>Required Accuracy</th>
                  <th>Delta</th>
                  <th>Status</th>
                </tr>
                <xsl:for-each select="Test">
                  <xsl:choose>
                    <xsl:when test="contains(state,'passed') or contains(passed,'true')">
                      <tr>
                        <td><xsl:value-of select="@var"/></td>
                        <td><xsl:value-of select="@mode"/></td>
                        <td><xsl:value-of select="eps"/></td>
                        <td><xsl:value-of select="delta"/></td>
                        <td align="center"><img src="ok.png"/></td>
                      </tr>
                    </xsl:when>
                    <xsl:otherwise>
                      <tr bgcolor="#cdba2d">
                        <td><xsl:value-of select="@var"/></td>
                        <td><xsl:value-of select="@mode"/></td>
                        <td><xsl:value-of select="eps"/></td>
                        <td><xsl:value-of select="delta"/></td>
                        <td align="center"><img src="nok.png"/></td>
                      </tr>
                    </xsl:otherwise>
                  </xsl:choose>
                </xsl:for-each>
              </table><br/>
              <xsl:for-each select="Test">
                <xsl:variable name="plotname" select="plot"/>
                <xsl:if test="$plotname">
                  <xsl:variable name="varname" select="@var"/>
                  <img style="margin-right:3px; margin-bottom:3px;" src="{plot}" alt="" title="" />
                  <br/><br/>
                </xsl:if>

              </xsl:for-each>
              <br/>
            </p>
          </div>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>